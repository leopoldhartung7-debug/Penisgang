import os
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional

from .account import Account
from .webhook import DiscordWebhook


class OutputWriter:
    """Thread-safe writer: combo file + JSONL audit file per platform + optional webhook."""

    def __init__(
        self,
        directory: str,
        fmt: str = "user:pass:token",
        webhook: Optional[DiscordWebhook] = None,
    ):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.fmt = fmt
        self.webhook = webhook
        self.lock = threading.Lock()
        self.session_tag = datetime.utcnow().strftime("%Y%m%d_%H%M%S")

    def _paths(self, platform: str):
        base = self.dir / platform
        base.mkdir(parents=True, exist_ok=True)
        combo = base / f"{platform}_{self.session_tag}.txt"
        full = base / f"{platform}_{self.session_tag}.jsonl"
        return combo, full

    def write(self, account: Account) -> None:
        combo_path, full_path = self._paths(account.platform)
        with self.lock:
            with open(combo_path, "a", encoding="utf-8") as f:
                f.write(account.to_combo(self.fmt) + "\n")
            with open(full_path, "a", encoding="utf-8") as f:
                f.write(account.to_json() + "\n")
        if self.webhook:
            self.webhook.send_account(account)
