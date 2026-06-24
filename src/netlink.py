"""Helpers to print a phone-friendly URL: LAN IP, QR code, optional tunnel."""
import io
import socket
import subprocess
import sys
import threading
import time
from typing import Optional


def lan_ip() -> str:
    """Best-effort local LAN IP — opens a UDP socket to a public addr (no packet sent)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


def print_qr(url: str) -> None:
    try:
        import qrcode
    except ImportError:
        print(f"  (install qrcode for terminal QR: pip install qrcode)")
        return
    qr = qrcode.QRCode(border=1, box_size=1)
    qr.add_data(url)
    qr.make()
    buf = io.StringIO()
    qr.print_ascii(out=buf, invert=True)
    print(buf.getvalue())


def start_cloudflare_tunnel(port: int) -> Optional[threading.Thread]:
    """Launch `cloudflared tunnel --url http://localhost:<port>` in the background.

    No login required — Cloudflare gives a random https://*.trycloudflare.com URL.
    Returns the thread (so caller can keep main alive). Prints the URL when it appears.
    """
    try:
        subprocess.run(["cloudflared", "--version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  cloudflared not installed — see README for install (1 command)")
        return None

    def _run():
        proc = subprocess.Popen(
            ["cloudflared", "tunnel", "--url", f"http://localhost:{port}"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
        url_printed = False
        for line in proc.stdout:
            if not url_printed and "trycloudflare.com" in line:
                import re

                m = re.search(r"https://[a-z0-9-]+\.trycloudflare\.com", line)
                if m:
                    url = m.group(0)
                    print("\n" + "=" * 60)
                    print(f"  PUBLIC URL (works anywhere):  {url}")
                    print("=" * 60)
                    print_qr(url)
                    url_printed = True

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t


def start_ngrok_tunnel(port: int, authtoken: Optional[str] = None) -> Optional[threading.Thread]:
    """Launch ngrok if installed (needs free signup for authtoken)."""
    try:
        subprocess.run(["ngrok", "version"], capture_output=True, check=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        print("  ngrok not installed — use --tunnel cloudflare instead")
        return None

    args = ["ngrok", "http", str(port), "--log=stdout"]
    if authtoken:
        args += ["--authtoken", authtoken]

    def _run():
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
        for line in proc.stdout:
            if "url=https://" in line:
                import re

                m = re.search(r"url=(https://[^\s]+\.ngrok[^\s]+)", line)
                if m:
                    url = m.group(1)
                    print("\n" + "=" * 60)
                    print(f"  PUBLIC URL (works anywhere):  {url}")
                    print("=" * 60)
                    print_qr(url)
                    break

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t
