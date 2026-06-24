import email
import imaplib
import re
import time
import uuid
from typing import Optional, Tuple

import httpx


class MailError(RuntimeError):
    pass


class MailTm:
    """mail.tm disposable inbox — public API, no key required."""

    BASE = "https://api.mail.tm"

    def __init__(self):
        self.client = httpx.Client(timeout=30, http2=True)
        self.address: Optional[str] = None
        self.password: Optional[str] = None
        self.token: Optional[str] = None

    def _domain(self) -> str:
        r = self.client.get(f"{self.BASE}/domains").json()
        return r["hydra:member"][0]["domain"]

    def create(self) -> Tuple[str, str]:
        domain = self._domain()
        local = uuid.uuid4().hex[:14]
        self.address = f"{local}@{domain}"
        self.password = uuid.uuid4().hex
        self.client.post(
            f"{self.BASE}/accounts",
            json={"address": self.address, "password": self.password},
        ).raise_for_status()
        tok = self.client.post(
            f"{self.BASE}/token",
            json={"address": self.address, "password": self.password},
        ).json()
        self.token = tok["token"]
        return self.address, self.password

    def _headers(self):
        return {"Authorization": f"Bearer {self.token}"}

    def wait_for_message(self, sender_contains: str = "", timeout: int = 180) -> dict:
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(4)
            r = self.client.get(f"{self.BASE}/messages", headers=self._headers()).json()
            for m in r.get("hydra:member", []):
                if sender_contains.lower() in (m.get("from", {}).get("address", "") + m.get("subject", "")).lower():
                    full = self.client.get(
                        f"{self.BASE}/messages/{m['id']}", headers=self._headers()
                    ).json()
                    return full
        raise MailError("mail timeout")

    @staticmethod
    def extract_link(body: str, pattern: str) -> Optional[str]:
        m = re.search(pattern, body)
        return m.group(0) if m else None

    @staticmethod
    def extract_code(body: str, pattern: str = r"\b\d{4,8}\b") -> Optional[str]:
        m = re.search(pattern, body)
        return m.group(0) if m else None


class ImapCatchall:
    """Catchall inbox via IMAP — pair with a domain that forwards *@domain to one mailbox."""

    def __init__(self, host: str, user: str, password: str, catchall_domain: str):
        self.host = host
        self.user = user
        self.password = password
        self.domain = catchall_domain

    def random_address(self) -> str:
        return f"{uuid.uuid4().hex[:12]}@{self.domain}"

    def wait_for(self, to_address: str, sender_contains: str, timeout: int = 180):
        deadline = time.time() + timeout
        while time.time() < deadline:
            time.sleep(5)
            with imaplib.IMAP4_SSL(self.host) as mbox:
                mbox.login(self.user, self.password)
                mbox.select("INBOX")
                typ, data = mbox.search(None, f'(TO "{to_address}")')
                for num in data[0].split():
                    typ, msg = mbox.fetch(num, "(RFC822)")
                    parsed = email.message_from_bytes(msg[0][1])
                    if sender_contains.lower() in parsed.get("From", "").lower():
                        body = ""
                        if parsed.is_multipart():
                            for part in parsed.walk():
                                if part.get_content_type() == "text/html":
                                    body = part.get_payload(decode=True).decode(errors="ignore")
                                    break
                        else:
                            body = parsed.get_payload(decode=True).decode(errors="ignore")
                        return body
        raise MailError("imap timeout")


def build(config: dict):
    provider = config.get("provider", "mail_tm")
    if provider == "mail_tm":
        return MailTm()
    if provider == "imap":
        return ImapCatchall(
            config["imap_host"], config["imap_user"], config["imap_pass"], config["catchall_domain"]
        )
    raise MailError(f"unsupported mail provider: {provider}")
