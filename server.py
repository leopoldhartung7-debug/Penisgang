#!/usr/bin/env python3
"""FastAPI server — mobile-first UI for the account generator.

Run:
    python server.py
Then open http://<your-ip>:8000 from your iPhone Safari.
"""
import argparse
import asyncio
import json
import secrets
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, Header, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src import captcha as captcha_mod
from src import mail as mail_mod
from src.proxies import ProxyPool
from src.output import OutputWriter
from src.webhook import DiscordWebhook
from src.generators import REGISTRY
from src.tools.token_checker import DiscordTokenChecker
from src.tools.joiner import DiscordJoiner


CONFIG_PATH = Path("config.json")
STATIC_DIR = Path(__file__).parent / "static"


def load_config() -> dict:
    if not CONFIG_PATH.exists():
        raise SystemExit("config.json not found — copy config.example.json first")
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def save_config(cfg: dict) -> None:
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2, ensure_ascii=False), encoding="utf-8")


cfg = load_config()
captcha = captcha_mod.build(cfg["captcha"])
proxies = ProxyPool(cfg["proxies"].get("file"), cfg["proxies"].get("scheme", "http"))
webhook = DiscordWebhook(
    url=cfg.get("webhook", {}).get("url") or None,
    username=cfg.get("webhook", {}).get("username", "AccGen"),
    enabled=cfg.get("webhook", {}).get("enabled", False),
)
writer = OutputWriter(
    cfg["output"]["directory"],
    cfg["output"].get("format", "user:pass:token"),
    webhook=webhook,
)
executor = ThreadPoolExecutor(max_workers=cfg.get("threads", 5))

event_queue: asyncio.Queue = asyncio.Queue()
AUTH_TOKEN: str = cfg.get("server", {}).get("auth_token") or ""


def push_event(kind: str, **data):
    try:
        event_queue.put_nowait({"kind": kind, **data})
    except Exception:
        pass


app = FastAPI(title="AccGen", docs_url=None, redoc_url=None)
app.add_middleware(
    CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def check_auth(x_auth_token: Optional[str]):
    if AUTH_TOKEN and x_auth_token != AUTH_TOKEN:
        raise HTTPException(401, "invalid auth token")


class GenerateReq(BaseModel):
    platform: str
    amount: int = 1


class WebhookReq(BaseModel):
    url: Optional[str] = None
    enabled: bool = True


class TokensReq(BaseModel):
    tokens: list[str]


class JoinReq(BaseModel):
    tokens: list[str]
    invite: str
    delay_ms: int = 800


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC_DIR / "index.html").read_text(encoding="utf-8")


@app.get("/api/status")
def status():
    return {
        "platforms": list(REGISTRY.keys()),
        "webhook_enabled": webhook.enabled,
        "webhook_set": bool(webhook.url),
        "proxies": len(proxies.proxies),
        "auth_required": bool(AUTH_TOKEN),
    }


@app.post("/api/webhook")
def set_webhook(req: WebhookReq, x_auth_token: Optional[str] = Header(default=None)):
    check_auth(x_auth_token)
    webhook.set_url(req.url if req.enabled else None)
    cfg.setdefault("webhook", {})
    cfg["webhook"]["url"] = req.url or ""
    cfg["webhook"]["enabled"] = bool(req.enabled and req.url)
    save_config(cfg)
    push_event("webhook", enabled=webhook.enabled)
    if webhook.enabled:
        webhook.send_status("🟢 AccGen webhook connected", color=0x57F287)
    return {"ok": True, "enabled": webhook.enabled}


def _run_one(platform: str):
    cls = REGISTRY[platform]
    mail = mail_mod.build(cfg["mail"])
    gen = cls(captcha, mail, proxies, verbose=False)
    push_event("log", message=f"[{platform}] starting…")
    try:
        acc = gen.generate()
    except Exception as e:
        push_event("log", message=f"[{platform}] error: {e}")
        return None
    if not acc:
        push_event("log", message=f"[{platform}] failed")
        return None
    writer.write(acc)
    push_event("account", platform=platform, username=acc.username, email=acc.email)
    return acc


@app.post("/api/generate")
async def generate(req: GenerateReq, x_auth_token: Optional[str] = Header(default=None)):
    check_auth(x_auth_token)
    if req.platform != "all" and req.platform not in REGISTRY:
        raise HTTPException(400, f"unknown platform: {req.platform}")
    if req.amount < 1 or req.amount > 500:
        raise HTTPException(400, "amount must be 1..500")

    platforms = list(REGISTRY.keys()) if req.platform == "all" else [req.platform]
    jobs = [platforms[i % len(platforms)] for i in range(req.amount)]

    loop = asyncio.get_event_loop()
    for p in jobs:
        loop.run_in_executor(executor, _run_one, p)

    return {"ok": True, "queued": req.amount}


@app.get("/api/events")
async def events(request: Request):
    async def stream():
        yield "event: ready\ndata: {}\n\n"
        while True:
            if await request.is_disconnected():
                break
            try:
                ev = await asyncio.wait_for(event_queue.get(), timeout=20.0)
                yield f"data: {json.dumps(ev)}\n\n"
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(stream(), media_type="text/event-stream")


@app.post("/api/check")
async def check_tokens(req: TokensReq, x_auth_token: Optional[str] = Header(default=None)):
    check_auth(x_auth_token)
    checker = DiscordTokenChecker(proxies=proxies)
    loop = asyncio.get_event_loop()

    async def run():
        results = []
        for tok in req.tokens:
            res = await loop.run_in_executor(executor, checker.check, tok)
            push_event("check", token=tok[:24] + "…", **res)
            results.append({"token": tok, **res})
        if webhook.enabled:
            ok = sum(1 for r in results if r.get("valid"))
            webhook.send_status(
                f"🔎 Checked {len(results)} tokens — {ok} valid / {len(results) - ok} invalid",
                color=0x5865F2,
            )
        return results

    asyncio.create_task(run())
    return {"ok": True, "queued": len(req.tokens)}


@app.post("/api/join")
async def join_invite(req: JoinReq, x_auth_token: Optional[str] = Header(default=None)):
    check_auth(x_auth_token)
    joiner = DiscordJoiner(
        captcha=captcha,
        proxies=proxies,
        delay_ms=req.delay_ms,
    )
    loop = asyncio.get_event_loop()

    async def run():
        for tok in req.tokens:
            res = await loop.run_in_executor(executor, joiner.join, tok, req.invite)
            push_event("join", token=tok[:24] + "…", invite=req.invite, **res)
        if webhook.enabled:
            webhook.send_status(
                f"🚪 Join sweep finished — {len(req.tokens)} tokens → `{req.invite}`",
                color=0x57F287,
            )

    asyncio.create_task(run())
    return {"ok": True, "queued": len(req.tokens)}


if __name__ == "__main__":
    import uvicorn

    from src.netlink import lan_ip, print_qr, start_cloudflare_tunnel, start_ngrok_tunnel

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default=cfg.get("server", {}).get("host", "0.0.0.0"))
    parser.add_argument("--port", type=int, default=cfg.get("server", {}).get("port", 8000))
    parser.add_argument(
        "--tunnel",
        choices=["none", "cloudflare", "ngrok"],
        default="none",
        help="public https URL via cloudflared (no signup) or ngrok",
    )
    parser.add_argument("--ngrok-token", default=None, help="ngrok authtoken if using --tunnel ngrok")
    args = parser.parse_args()

    ip = lan_ip()
    lan_url = f"http://{ip}:{args.port}"

    print("\n" + "=" * 60)
    print(f"  AccGen running on  →  {lan_url}")
    print("=" * 60)
    print("  same WiFi as your iPhone? scan this QR with the camera:")
    print()
    print_qr(lan_url)

    if not AUTH_TOKEN:
        print("  ⚠ no server.auth_token set — anyone on your network can hit the API")

    if args.tunnel == "cloudflare":
        print("  starting cloudflare tunnel… (free, no signup)")
        start_cloudflare_tunnel(args.port)
    elif args.tunnel == "ngrok":
        print("  starting ngrok tunnel…")
        start_ngrok_tunnel(args.port, args.ngrok_token)

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")
