import re
import time
from typing import Optional

import tls_client

from .base import BaseGenerator
from ..account import Account
from ..names import random_username, random_password


STEAM_JOIN_URL = "https://store.steampowered.com/join/"
STEAM_HCAPTCHA_SITEKEY = "6d569255-fa07-435e-99eb-2f8d49f3be17"
STEAM_AJAX_VERIFY = "https://store.steampowered.com/join/ajaxverifyemail"
STEAM_AJAX_CHECK = "https://store.steampowered.com/join/ajaxcheckemailverified"
STEAM_AJAX_AVAILABLE = "https://store.steampowered.com/join/checkavail/"
STEAM_AJAX_CREATE = "https://store.steampowered.com/join/createaccount/"


class SteamGenerator(BaseGenerator):
    name = "steam"

    def _session(self, proxy: Optional[str]):
        s = tls_client.Session(client_identifier="chrome_124", random_tls_extension_order=True)
        if proxy:
            s.proxies = {"http": proxy, "https": proxy}
        s.headers.update(
            {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en-US,en;q=0.9",
                "Origin": "https://store.steampowered.com",
                "Referer": STEAM_JOIN_URL,
            }
        )
        return s

    def _username_available(self, s, username: str) -> bool:
        r = s.post(STEAM_AJAX_AVAILABLE, data={"accountname": username, "count": 1}).json()
        return r.get("bAvailable", False)

    def generate(self) -> Optional[Account]:
        proxy = self.proxies.next()
        self.log(f"using proxy: {proxy or 'direct'}")

        email, _ = self.mail.create()
        password = random_password()

        s = self._session(proxy)
        s.get(STEAM_JOIN_URL)

        self.log("solving hCaptcha…")
        captcha_token = self.captcha.hcaptcha(STEAM_HCAPTCHA_SITEKEY, STEAM_JOIN_URL, proxy)

        verify = s.post(
            STEAM_AJAX_VERIFY,
            data={
                "email": email,
                "captcha_text": "",
                "captchagid": -1,
                "captcha_token": captcha_token,
                "elang": 0,
            },
        ).json()

        creation_id = verify.get("sessionid") or verify.get("createaccount_token")
        if not creation_id and verify.get("success") != 1:
            self.log(f"verify failed: {verify}")
            return None

        self.log("waiting for steam verification mail…")
        try:
            msg = self.mail.wait_for_message(sender_contains="steam", timeout=180)
            body = msg.get("html", [""])[0] if msg.get("html") else msg.get("text", "")
            link = self.mail.extract_link(
                body, r"https://store\.steampowered\.com/account/newaccountverification[^\s\"'>]+"
            )
            if link:
                s.get(link)
                self.log("email verified")
        except Exception as e:
            self.log(f"mail verify failed: {e}")
            return None

        for _ in range(20):
            time.sleep(3)
            chk = s.post(STEAM_AJAX_CHECK, data={"creationid": creation_id}).json()
            if chk.get("bEmailVerified"):
                break

        username = random_username(8, 14)
        for _ in range(5):
            if self._username_available(s, username):
                break
            username = random_username(8, 14)

        create = s.post(
            STEAM_AJAX_CREATE,
            data={
                "accountname": username,
                "password": password,
                "count": 26,
                "lt": 0,
                "creation_id": creation_id,
            },
        ).json()

        if not create.get("bSuccess"):
            self.log(f"create failed: {create}")
            return None

        return Account(
            platform=self.name,
            email=email,
            username=username,
            password=password,
            user_id=create.get("steamid"),
            proxy=proxy,
        )
