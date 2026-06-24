from abc import ABC, abstractmethod
from typing import Optional

from ..account import Account
from ..captcha import TwoCaptcha
from ..mail import MailTm, ImapCatchall
from ..proxies import ProxyPool


class BaseGenerator(ABC):
    name: str = "base"

    def __init__(self, captcha: TwoCaptcha, mail, proxies: ProxyPool, verbose: bool = False):
        self.captcha = captcha
        self.mail = mail
        self.proxies = proxies
        self.verbose = verbose

    def log(self, msg: str) -> None:
        if self.verbose:
            print(f"[{self.name}] {msg}")

    @abstractmethod
    def generate(self) -> Optional[Account]:
        ...
