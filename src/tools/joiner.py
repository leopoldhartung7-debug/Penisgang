"""Discord mass joiner — uses tokens to join a guild via invite code.

POST /invites/{code} with the token in Authorization.
Handles hCaptcha challenges (rcaptcha sitekey returned in the 400 body).
"""
import base64
import json
import re
import time
from typing import Optional

import tls_client

from ..captcha import TwoCaptcha
from ..proxies import ProxyPool


DISCORD_API = "https://discord.com/api/v9"
DEFAULT_HCAPTCHA_SITEKEY = "4c672d35-0701-42b2-88c3-78380b0db560"


def _super_props() -> str:
    payload = {
        "os": "Windows", "browser": "Chrome", "device": "",
        "system_locale": "en-US",
        "browser_user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "browser_version": "124.0.0.0", "os_version": "10",
        "referrer": "", "referring_domain": "",
        "referrer_current": "", "referring_domain_current": "",
        "release_channel": "stable", "client_build_number": 290000,
        "client_event_source": None,
    }
    return base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()


class DiscordJoiner:
    def __init__(
        self,
        captcha: Optional[TwoCaptcha] = None,
        proxies: Optional[ProxyPool] = None,
        delay_ms: int = 800,
    ):
        self.captcha = captcha
        self.proxies = proxies
        self.delay_ms = delay_ms

    @staticmethod
    def normalize_invite(invite: str) -> str:
        m = re.search(r"(?:discord\.gg/|discord\.com/invite/)([A-Za-z0-9-]+)", invite)
        return m.group(1) if m else invite.strip().lstrip("/")

    def _session(self, token: str, proxy: Optional[str]):
        s = tls_client.Session(client_identifier="chrome_124", random_tls_extension_order=True)
        if proxy:
            s.proxies = {"http": proxy, "https": proxy}
        s.headers.update(
            {
                "Authorization": token.strip(),
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://discord.com",
                "Referer": "https://discord.com/channels/@me",
                "X-Super-Properties": _super_props(),
                "X-Discord-Locale": "en-US",
                "X-Debug-Options": "bugReporterEnabled",
                "Content-Type": "application/json",
            }
        )
        return s

    def join(self, token: str, invite: str) -> dict:
        code = self.normalize_invite(invite)
        proxy = self.proxies.next() if self.proxies else None

        try:
            s = self._session(token, proxy)
        except Exception as e:
            return {"success": False, "reason": f"session:{e}"}

        endpoint = f"{DISCORD_API}/invites/{code}"

        try:
            r = s.post(endpoint, json={})
        except Exception as e:
            return {"success": False, "reason": f"network:{e}"}

        if r.status_code == 200:
            time.sleep(self.delay_ms / 1000)
            data = r.json() if r.text else {}
            return {
                "success": True,
                "reason": "joined",
                "guild_id": (data.get("guild") or {}).get("id"),
                "guild_name": (data.get("guild") or {}).get("name"),
            }

        if r.status_code == 401:
            return {"success": False, "reason": "unauthorized"}
        if r.status_code == 403:
            return {"success": False, "reason": "forbidden"}
        if r.status_code == 429:
            retry = r.json().get("retry_after", 1) if r.text else 1
            return {"success": False, "reason": f"rate_limited:{retry}"}

        body = {}
        try:
            body = r.json()
        except Exception:
            return {"success": False, "reason": f"http_{r.status_code}"}

        if "captcha_key" in body and self.captcha:
            sitekey = body.get("captcha_sitekey") or DEFAULT_HCAPTCHA_SITEKEY
            try:
                captcha_token = self.captcha.hcaptcha(
                    sitekey, f"https://discord.com/invite/{code}", proxy
                )
            except Exception as e:
                return {"success": False, "reason": f"captcha:{e}"}
            s.headers["X-Captcha-Key"] = captcha_token
            try:
                r2 = s.post(endpoint, json={"captcha_key": captcha_token, "captcha_rqtoken": body.get("captcha_rqtoken", "")})
            except Exception as e:
                return {"success": False, "reason": f"network:{e}"}
            if r2.status_code == 200:
                time.sleep(self.delay_ms / 1000)
                data = r2.json() if r2.text else {}
                return {
                    "success": True,
                    "reason": "joined_after_captcha",
                    "guild_id": (data.get("guild") or {}).get("id"),
                    "guild_name": (data.get("guild") or {}).get("name"),
                }
            return {"success": False, "reason": f"after_captcha_{r2.status_code}"}

        if body.get("message"):
            return {"success": False, "reason": body["message"][:120]}
        return {"success": False, "reason": f"http_{r.status_code}"}
