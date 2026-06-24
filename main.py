#!/usr/bin/env python3
"""Account generator CLI — discord / steam / rockstar."""

import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from colorama import Fore, Style, init as colorama_init

from src import captcha as captcha_mod
from src import mail as mail_mod
from src.proxies import ProxyPool
from src.output import OutputWriter
from src.generators import REGISTRY


BANNER = r"""
   ___                          _    ___
  / _ \  __ ___ ___ _   _ _ _  | |_ / __|___ _ _
 | (_) |/ _/ _/ _ \ | | | ' \  |  _| (_ / -_) ' \
  \___/ \__\__\___/\_,_|_||_|  \__|\___\___|_||_|
       discord  ·  steam  ·  rockstar
"""


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        print(f"{Fore.RED}config not found: {path}{Style.RESET_ALL}")
        print("copy config.example.json → config.json and fill it in")
        sys.exit(1)
    return json.loads(p.read_text(encoding="utf-8"))


def build_runtime(cfg: dict):
    cap = captcha_mod.build(cfg["captcha"])
    pool = ProxyPool(cfg["proxies"].get("file"), cfg["proxies"].get("scheme", "http"))
    writer = OutputWriter(cfg["output"]["directory"], cfg["output"].get("format", "user:pass:token"))
    return cap, pool, writer


def make_generator(platform: str, cap, pool, cfg):
    cls = REGISTRY.get(platform)
    if not cls:
        raise SystemExit(f"unknown platform: {platform}")
    mail = mail_mod.build(cfg["mail"])
    return cls(cap, mail, pool, verbose=cfg.get("verbose", True))


def menu() -> tuple[str, int]:
    print(BANNER)
    print(f"{Fore.CYAN}1{Style.RESET_ALL}) discord")
    print(f"{Fore.CYAN}2{Style.RESET_ALL}) steam")
    print(f"{Fore.CYAN}3{Style.RESET_ALL}) rockstar")
    print(f"{Fore.CYAN}4{Style.RESET_ALL}) all (round-robin)")
    choice = input(f"{Fore.YELLOW}plattform> {Style.RESET_ALL}").strip()
    mapping = {"1": "discord", "2": "steam", "3": "rockstar", "4": "all"}
    platform = mapping.get(choice, choice)
    if platform not in {*REGISTRY.keys(), "all"}:
        print(f"{Fore.RED}invalid choice{Style.RESET_ALL}")
        sys.exit(1)
    amount = int(input(f"{Fore.YELLOW}menge> {Style.RESET_ALL}").strip() or "1")
    return platform, amount


def run_one(platform: str, cap, pool, cfg, writer: OutputWriter) -> bool:
    gen = make_generator(platform, cap, pool, cfg)
    try:
        acc = gen.generate()
    except Exception as e:
        print(f"{Fore.RED}[{platform}] error: {e}{Style.RESET_ALL}")
        return False
    if not acc:
        print(f"{Fore.RED}[{platform}] failed{Style.RESET_ALL}")
        return False
    writer.write(acc)
    print(f"{Fore.GREEN}[{platform}] ✓ {acc.username} | {acc.email}{Style.RESET_ALL}")
    return True


def main():
    colorama_init(autoreset=True)
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config.json")
    parser.add_argument("--platform", choices=[*REGISTRY.keys(), "all"])
    parser.add_argument("--amount", type=int, default=0)
    parser.add_argument("--threads", type=int, default=0)
    args = parser.parse_args()

    cfg = load_config(args.config)

    if args.platform and args.amount:
        platform, amount = args.platform, args.amount
    else:
        platform, amount = menu()

    cap, pool, writer = build_runtime(cfg)
    threads = args.threads or cfg.get("threads", 5)

    platforms = list(REGISTRY.keys()) if platform == "all" else [platform]
    jobs = [(platforms[i % len(platforms)]) for i in range(amount)]

    started = time.time()
    successes = 0
    with ThreadPoolExecutor(max_workers=threads) as pool_ex:
        futs = [pool_ex.submit(run_one, p, cap, pool, cfg, writer) for p in jobs]
        for f in as_completed(futs):
            if f.result():
                successes += 1

    dur = time.time() - started
    print(
        f"\n{Fore.MAGENTA}done — {successes}/{amount} accounts in {dur:.1f}s "
        f"→ {cfg['output']['directory']}/{Style.RESET_ALL}"
    )


if __name__ == "__main__":
    main()
