"""Discord webhook delivery — sends each generated account as an embed."""
import threading
from typing import Optional

import httpx

from .account import Account


PLATFORM_COLORS = {
    "discord": 0x5865F2,
    "steam": 0x1B2838,
    "rockstar": 0xFCAF17,
}

PLATFORM_ICONS = {
    "discord": "https://assets-global.website-files.com/6257adef93867e50d84d30e2/636e0a6a49cf127bf92de1e2_icon_clyde_blurple_RGB.png",
    "steam": "https://upload.wikimedia.org/wikipedia/commons/8/83/Steam_icon_logo.svg",
    "rockstar": "https://upload.wikimedia.org/wikipedia/commons/d/d0/Rockstar_Games_Logo.svg",
}


class DiscordWebhook:
    """Thread-safe Discord webhook sender."""

    def __init__(self, url: Optional[str] = None, username: str = "AccGen", enabled: bool = True):
        self.url = url
        self.username = username
        self.enabled = enabled and bool(url)
        self.client = httpx.Client(timeout=15, http2=True)
        self.lock = threading.Lock()

    def set_url(self, url: Optional[str]) -> None:
        with self.lock:
            self.url = url
            self.enabled = bool(url)

    def send_account(self, account: Account) -> bool:
        if not self.enabled or not self.url:
            return False

        color = PLATFORM_COLORS.get(account.platform, 0x2F3136)
        icon = PLATFORM_ICONS.get(account.platform)

        fields = [
            {"name": "Username", "value": f"`{account.username}`", "inline": True},
            {"name": "Email", "value": f"`{account.email}`", "inline": True},
            {"name": "Password", "value": f"`{account.password}`", "inline": False},
        ]
        if account.token:
            tok = account.token if len(account.token) <= 1024 else account.token[:1020] + "…"
            fields.append({"name": "Token", "value": f"```{tok}```", "inline": False})
        if account.user_id:
            fields.append({"name": "ID", "value": f"`{account.user_id}`", "inline": True})
        if account.proxy:
            fields.append({"name": "Proxy", "value": f"`{account.proxy}`", "inline": True})
        for k, v in (account.extra or {}).items():
            fields.append({"name": k.title(), "value": f"`{v}`", "inline": True})

        embed = {
            "title": f"✓ {account.platform.title()} Account",
            "color": color,
            "fields": fields,
            "footer": {"text": "AccGen", "icon_url": icon} if icon else {"text": "AccGen"},
            "timestamp": account.created_at + "Z" if not account.created_at.endswith("Z") else account.created_at,
        }

        payload = {"username": self.username, "embeds": [embed]}
        try:
            with self.lock:
                r = self.client.post(self.url, json=payload)
            return r.status_code in (200, 204)
        except Exception:
            return False

    def send_status(self, message: str, color: int = 0x2F3136) -> bool:
        if not self.enabled or not self.url:
            return False
        payload = {
            "username": self.username,
            "embeds": [{"description": message, "color": color}],
        }
        try:
            with self.lock:
                r = self.client.post(self.url, json=payload)
            return r.status_code in (200, 204)
        except Exception:
            return False
