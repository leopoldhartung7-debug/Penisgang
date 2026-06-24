"""Discord token validator — hits /users/@me + /users/@me/billing.

Returns:
    valid: bool
    reason: short status (ok / unauthorized / locked / rate_limited / network)
    username: str or None
    id: str or None
    email: str or None
    phone: str or None
    mfa: bool
    verified: bool
    flags: int
    nitro: int (0 none, 1 classic, 2 nitro, 3 basic)
    billing: bool   (has any saved payment source)
"""
from typing import Optional

import tls_client

from ..proxies import ProxyPool


DISCORD_API = "https://discord.com/api/v9"


class DiscordTokenChecker:
    def __init__(self, proxies: Optional[ProxyPool] = None):
        self.proxies = proxies

    def _session(self, token: str, proxy: Optional[str]):
        s = tls_client.Session(client_identifier="chrome_124", random_tls_extension_order=True)
        if proxy:
            s.proxies = {"http": proxy, "https": proxy}
        s.headers.update(
            {
                "Authorization": token,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "*/*",
                "Origin": "https://discord.com",
                "Referer": "https://discord.com/channels/@me",
            }
        )
        return s

    def check(self, token: str) -> dict:
        proxy = self.proxies.next() if self.proxies else None
        token = token.strip()
        try:
            s = self._session(token, proxy)
            me = s.get(f"{DISCORD_API}/users/@me")
        except Exception as e:
            return {"valid": False, "reason": f"network:{e}"}

        if me.status_code == 401:
            return {"valid": False, "reason": "unauthorized"}
        if me.status_code == 403:
            return {"valid": False, "reason": "locked"}
        if me.status_code == 429:
            return {"valid": False, "reason": "rate_limited"}
        if me.status_code != 200:
            return {"valid": False, "reason": f"http_{me.status_code}"}

        try:
            data = me.json()
        except Exception:
            return {"valid": False, "reason": "bad_response"}

        billing = False
        try:
            b = s.get(f"{DISCORD_API}/users/@me/billing/payment-sources")
            if b.status_code == 200:
                billing = len(b.json() or []) > 0
        except Exception:
            pass

        return {
            "valid": True,
            "reason": "ok",
            "id": data.get("id"),
            "username": data.get("username"),
            "global_name": data.get("global_name"),
            "email": data.get("email"),
            "phone": data.get("phone"),
            "mfa": bool(data.get("mfa_enabled")),
            "verified": bool(data.get("verified")),
            "flags": data.get("flags", 0),
            "nitro": data.get("premium_type", 0),
            "billing": billing,
        }
