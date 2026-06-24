import random
import string
import secrets

from faker import Faker

_fake = Faker(["de_DE", "en_US", "es_ES", "it_IT", "ja_JP"])


def random_username(min_len: int = 8, max_len: int = 14) -> str:
    first = _fake.first_name().lower()
    last = _fake.last_name().lower()
    base = (first + last).replace(" ", "")[: max_len - 3]
    suffix = "".join(random.choices(string.digits, k=random.randint(2, 4)))
    out = base + suffix
    if len(out) < min_len:
        out += "".join(random.choices(string.ascii_lowercase, k=min_len - len(out)))
    return out


def random_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%&*"
    while True:
        pw = "".join(secrets.choice(alphabet) for _ in range(length))
        if (
            any(c.islower() for c in pw)
            and any(c.isupper() for c in pw)
            and any(c.isdigit() for c in pw)
            and any(c in "!@#$%&*" for c in pw)
        ):
            return pw


def random_dob(min_age: int = 22, max_age: int = 40):
    year = 2025 - random.randint(min_age, max_age)
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return year, month, day


def random_first_last():
    return _fake.first_name(), _fake.last_name()
