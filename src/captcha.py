import time
from typing import Optional

import httpx


class CaptchaError(RuntimeError):
    pass


class TwoCaptcha:
    """Thin 2captcha client supporting hCaptcha + reCaptcha v2."""

    BASE = "https://2captcha.com"

    def __init__(self, api_key: str, timeout: int = 180):
        self.api_key = api_key
        self.timeout = timeout
        self.client = httpx.Client(timeout=30, http2=True)

    def _submit(self, payload: dict) -> str:
        payload["key"] = self.api_key
        payload["json"] = 1
        r = self.client.post(f"{self.BASE}/in.php", data=payload).json()
        if r.get("status") != 1:
            raise CaptchaError(f"submit failed: {r.get('request')}")
        return r["request"]

    def _poll(self, captcha_id: str) -> str:
        deadline = time.time() + self.timeout
        while time.time() < deadline:
            time.sleep(5)
            r = self.client.get(
                f"{self.BASE}/res.php",
                params={"key": self.api_key, "action": "get", "id": captcha_id, "json": 1},
            ).json()
            if r.get("status") == 1:
                return r["request"]
            if r.get("request") != "CAPCHA_NOT_READY":
                raise CaptchaError(f"poll failed: {r.get('request')}")
        raise CaptchaError("captcha timeout")

    def hcaptcha(self, sitekey: str, url: str, proxy: Optional[str] = None) -> str:
        payload = {"method": "hcaptcha", "sitekey": sitekey, "pageurl": url}
        if proxy:
            payload.update({"proxy": proxy.split("://", 1)[-1], "proxytype": "HTTP"})
        return self._poll(self._submit(payload))

    def recaptcha_v2(self, sitekey: str, url: str, proxy: Optional[str] = None) -> str:
        payload = {"method": "userrecaptcha", "googlekey": sitekey, "pageurl": url}
        if proxy:
            payload.update({"proxy": proxy.split("://", 1)[-1], "proxytype": "HTTP"})
        return self._poll(self._submit(payload))


def build(config: dict) -> TwoCaptcha:
    if config.get("provider") != "2captcha":
        raise CaptchaError(f"unsupported captcha provider: {config.get('provider')}")
    return TwoCaptcha(config["api_key"], config.get("timeout", 180))
