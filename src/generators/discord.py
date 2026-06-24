import base64
import json
import time
from typing import Optional

import tls_client

from .base import BaseGenerator
from ..account import Account
from ..names import random_username, random_password, random_dob


DISCORD_API = "https://discord.com/api/v9"
DISCORD_HCAPTCHA_SITEKEY = "4c672d35-0701-42b2-88c3-78380b0db560"
DISCORD_REGISTER_URL = "https://discord.com/register"


class DiscordGenerator(BaseGenerator):
    name = "discord"

    def _session(self, proxy: Optional[str]):
        s = tls_client.Session(client_identifier="chrome_124", random_tls_extension_order=True)
        if proxy:
            s.proxies = {"http": proxy, "https": proxy}
        s.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://discord.com",
                "Referer": DISCORD_REGISTER_URL,
                "X-Discord-Locale": "en-US",
                "X-Debug-Options": "bugReporterEnabled",
            }
        )
        return s

    @staticmethod
    def _super_props() -> str:
        payload = {
            "os": "Windows",
            "browser": "Chrome",
            "device": "",
            "system_locale": "en-US",
            "browser_user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
            "browser_version": "124.0.0.0",
            "os_version": "10",
            "referrer": "",
            "referring_domain": "",
            "referrer_current": "",
            "referring_domain_current": "",
            "release_channel": "stable",
            "client_build_number": 290000,
            "client_event_source": None,
        }
        return base64.b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode()

    def _fingerprint(self, s) -> str:
        r = s.get(f"{DISCORD_API}/experiments")
        return r.json().get("fingerprint", "")

    def generate(self) -> Optional[Account]:
        proxy = self.proxies.next()
        self.log(f"using proxy: {proxy or 'direct'}")

        email, _ = self.mail.create()
        username = random_username()
        password = random_password()
        y, m, d = random_dob()
        self.log(f"mail={email} user={username}")

        s = self._session(proxy)
        s.headers["X-Super-Properties"] = self._super_props()
        fingerprint = self._fingerprint(s)
        s.headers["X-Fingerprint"] = fingerprint

        self.log("solving hCaptcha…")
        captcha_key = self.captcha.hcaptcha(
            DISCORD_HCAPTCHA_SITEKEY, DISCORD_REGISTER_URL, proxy
        )

        payload = {
            "fingerprint": fingerprint,
            "email": email,
            "username": username,
            "password": password,
            "global_name": username,
            "date_of_birth": f"{y:04d}-{m:02d}-{d:02d}",
            "consent": True,
            "gift_code_sku_id": None,
            "invite": None,
            "promotional_email_opt_in": False,
            "captcha_key": captcha_key,
        }
        r = s.post(f"{DISCORD_API}/auth/register", json=payload)
        data = r.json() if r.text else {}
        token = data.get("token")
        if not token:
            self.log(f"register failed: {r.status_code} {data}")
            return None

        self.log("waiting for verification mail…")
        try:
            msg = self.mail.wait_for_message(sender_contains="discord", timeout=120)
            body = msg.get("html", [""])[0] if msg.get("html") else msg.get("text", "")
            link = self.mail.extract_link(body, r"https://click\.discord\.com/[^\s\"'>]+")
            if link:
                s.get(link, allow_redirects=True)
                self.log("email verified")
        except Exception as e:
            self.log(f"mail verify skipped: {e}")

        return Account(
            platform=self.name,
            email=email,
            username=username,
            password=password,
            token=token,
            user_id=data.get("user_id"),
            proxy=proxy,
            extra={"dob": f"{y}-{m:02d}-{d:02d}"},
        )
