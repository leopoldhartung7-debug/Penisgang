#!/usr/bin/env python3
"""Account generator CLI — discord / steam / rockstar / check / join."""

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
from src.webhook import DiscordWebhook
from src.generators import REGISTRY
from src.tools.token_checker import DiscordTokenChecker
from src.tools.joiner import DiscordJoiner


BANNER = r"""
   ___                          _    ___
  / _ \  __ ___ ___ _   _ _ _  | |_ / __|___ _ _
 | (_) |/ _/ _/ _ \ | | | ' \  |  _| (_ / -_) ' \
  \___/ \__\__\___/\_,_|_||_|  \__|\___\___|_||_|
       discord  ·  steam  ·  rockstar  ·  check  ·  join
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
    wh_cfg = cfg.get("webhook", {})
    webhook = DiscordWebhook(
        url=wh_cfg.get("url") or None,
        username=wh_cfg.get("username", "AccGen"),
        enabled=wh_cfg.get("enabled", False),
    )
    writer = OutputWriter(
        cfg["output"]["directory"],
        cfg["output"].get("format", "user:pass:token"),
        webhook=webhook,
    )
    return cap, pool, writer, webhook


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


def cmd_generate(args, cfg):
    if args.platform and args.amount:
        platform, amount = args.platform, args.amount
    else:
        platform, amount = menu()

    cap, pool, writer, _ = build_runtime(cfg)
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


def cmd_check(args, cfg):
    tokens = _read_lines(args.file or args.tokens)
    if not tokens:
        print(f"{Fore.RED}no tokens{Style.RESET_ALL}")
        sys.exit(1)

    pool = ProxyPool(cfg["proxies"].get("file"), cfg["proxies"].get("scheme", "http"))
    checker = DiscordTokenChecker(proxies=pool)
    wh_cfg = cfg.get("webhook", {})
    webhook = DiscordWebhook(wh_cfg.get("url"), wh_cfg.get("username", "AccGen"), wh_cfg.get("enabled", False))

    valid_path = Path("output") / "tokens_valid.txt"
    invalid_path = Path("output") / "tokens_invalid.txt"
    valid_path.parent.mkdir(parents=True, exist_ok=True)

    threads = args.threads or cfg.get("threads", 5)
    ok = bad = 0
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = {ex.submit(checker.check, t): t for t in tokens}
        for fut in as_completed(futs):
            tok = futs[fut]
            res = fut.result()
            tag = f"{Fore.GREEN}VALID  " if res.get("valid") else f"{Fore.RED}INVALID"
            extra = res.get("username") or res.get("reason", "")
            print(f"{tag}{Style.RESET_ALL} {tok[:30]}… · {extra}")
            target = valid_path if res.get("valid") else invalid_path
            with open(target, "a", encoding="utf-8") as f:
                f.write(tok + "\n")
            if res.get("valid"):
                ok += 1
            else:
                bad += 1

    if webhook.enabled:
        webhook.send_status(f"🔎 Checked {len(tokens)} tokens — {ok} valid / {bad} invalid", 0x5865F2)
    print(f"\n{Fore.MAGENTA}done — {ok} valid / {bad} invalid → output/{Style.RESET_ALL}")


def cmd_join(args, cfg):
    tokens = _read_lines(args.file or args.tokens)
    if not tokens or not args.invite:
        print(f"{Fore.RED}need --invite + tokens{Style.RESET_ALL}")
        sys.exit(1)

    cap = captcha_mod.build(cfg["captcha"])
    pool = ProxyPool(cfg["proxies"].get("file"), cfg["proxies"].get("scheme", "http"))
    wh_cfg = cfg.get("webhook", {})
    webhook = DiscordWebhook(wh_cfg.get("url"), wh_cfg.get("username", "AccGen"), wh_cfg.get("enabled", False))
    joiner = DiscordJoiner(captcha=cap, proxies=pool, delay_ms=args.delay_ms)

    threads = args.threads or cfg.get("threads", 5)
    ok = bad = 0
    with ThreadPoolExecutor(max_workers=threads) as ex:
        futs = {ex.submit(joiner.join, t, args.invite): t for t in tokens}
        for fut in as_completed(futs):
            tok = futs[fut]
            res = fut.result()
            tag = f"{Fore.GREEN}JOINED " if res.get("success") else f"{Fore.RED}FAIL   "
            print(f"{tag}{Style.RESET_ALL} {tok[:30]}… · {res.get('reason', '')}")
            if res.get("success"):
                ok += 1
            else:
                bad += 1

    if webhook.enabled:
        webhook.send_status(f"🚪 Join sweep `{args.invite}` — {ok} joined / {bad} failed", 0x57F287)
    print(f"\n{Fore.MAGENTA}done — {ok} joined / {bad} failed{Style.RESET_ALL}")


def _read_lines(arg) -> list[str]:
    if not arg:
        return []
    if isinstance(arg, list):
        return [x.strip() for x in arg if x.strip()]
    p = Path(arg)
    if p.exists():
        return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [arg]


def main():
    colorama_init(autoreset=True)
    parser = argparse.ArgumentParser(prog="accgen")
    parser.add_argument("--config", default="config.json")
    sub = parser.add_subparsers(dest="cmd")

    p_gen = sub.add_parser("gen", help="generate accounts")
    p_gen.add_argument("--platform", choices=[*REGISTRY.keys(), "all"])
    p_gen.add_argument("--amount", type=int, default=0)
    p_gen.add_argument("--threads", type=int, default=0)

    p_check = sub.add_parser("check", help="validate discord tokens")
    p_check.add_argument("--file", help="path to token list (one per line)")
    p_check.add_argument("--tokens", nargs="+", help="inline tokens")
    p_check.add_argument("--threads", type=int, default=0)

    p_join = sub.add_parser("join", help="mass join discord invite")
    p_join.add_argument("--invite", required=True, help="invite code or full URL")
    p_join.add_argument("--file", help="path to token list")
    p_join.add_argument("--tokens", nargs="+", help="inline tokens")
    p_join.add_argument("--delay-ms", type=int, default=800, dest="delay_ms")
    p_join.add_argument("--threads", type=int, default=0)

    # legacy: bare `python main.py --platform ... --amount ...`
    parser.add_argument("--platform", choices=[*REGISTRY.keys(), "all"])
    parser.add_argument("--amount", type=int, default=0)
    parser.add_argument("--threads", type=int, default=0)

    args = parser.parse_args()
    cfg = load_config(args.config)

    if args.cmd == "check":
        return cmd_check(args, cfg)
    if args.cmd == "join":
        return cmd_join(args, cfg)
    return cmd_generate(args, cfg)


if __name__ == "__main__":
    main()
