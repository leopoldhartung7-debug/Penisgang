import re
from typing import Optional

import tls_client

from .base import BaseGenerator
from ..account import Account
from ..names import random_username, random_password, random_dob, random_first_last


SIGNIN_BASE = "https://signin.rockstargames.com"
RS_SIGNUP_URL = f"{SIGNIN_BASE}/signup"
RS_REGISTER_API = f"{SIGNIN_BASE}/api/signin/register"
RS_HCAPTCHA_SITEKEY = "65c3d426-ad5e-4d5d-95f1-0a7e1d2155b6"


class RockstarGenerator(BaseGenerator):
    name = "rockstar"

    def _session(self, proxy: Optional[str]):
        s = tls_client.Session(client_identifier="chrome_124", random_tls_extension_order=True)
        if proxy:
            s.proxies = {"http": proxy, "https": proxy}
        s.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept": "application/json, text/plain, */*",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": SIGNIN_BASE,
                "Referer": RS_SIGNUP_URL,
                "X-Requested-With": "XMLHttpRequest",
            }
        )
        return s

    def _csrf(self, s) -> Optional[str]:
        r = s.get(RS_SIGNUP_URL)
        m = re.search(r'name="csrf-token"\s+content="([^"]+)"', r.text)
        if m:
            s.headers["X-CSRF-TOKEN"] = m.group(1)
            return m.group(1)
        return None

    def generate(self) -> Optional[Account]:
        proxy = self.proxies.next()
        self.log(f"using proxy: {proxy or 'direct'}")

        email, _ = self.mail.create()
        nickname = random_username(6, 12)
        password = random_password(18)
        first, last = random_first_last()
        y, m, d = random_dob(min_age=25, max_age=40)

        s = self._session(proxy)
        self._csrf(s)

        self.log("solving hCaptcha…")
        captcha_token = self.captcha.hcaptcha(RS_HCAPTCHA_SITEKEY, RS_SIGNUP_URL, proxy)

        payload = {
            "nickname": nickname,
            "email": email,
            "emailConfirm": email,
            "password": password,
            "passwordConfirm": password,
            "country": "DE",
            "firstName": first,
            "lastName": last,
            "dob": f"{y:04d}-{m:02d}-{d:02d}",
            "newsletter": False,
            "thirdPartyEmail": False,
            "captcha": captcha_token,
            "language": "de",
        }
        r = s.post(RS_REGISTER_API, json=payload)
        data = r.json() if r.text else {}

        if r.status_code != 200 or not (data.get("success") or data.get("rockstarId")):
            self.log(f"register failed: {r.status_code} {data}")
            return None

        self.log("waiting for verification mail…")
        try:
            msg = self.mail.wait_for_message(sender_contains="rockstargames", timeout=180)
            body = msg.get("html", [""])[0] if msg.get("html") else msg.get("text", "")
            link = self.mail.extract_link(
                body, r"https://signin\.rockstargames\.com/[^\s\"'>]*confirm[^\s\"'>]+"
            )
            if link:
                s.get(link, allow_redirects=True)
                self.log("email verified")
        except Exception as e:
            self.log(f"mail verify skipped: {e}")

        return Account(
            platform=self.name,
            email=email,
            username=nickname,
            password=password,
            user_id=str(data.get("rockstarId", "")),
            proxy=proxy,
            extra={
                "first": first,
                "last": last,
                "dob": f"{y}-{m:02d}-{d:02d}",
                "country": "DE",
            },
        )
