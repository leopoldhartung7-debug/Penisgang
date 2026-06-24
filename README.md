# Account Generator + Token Checker + Joiner

Modulares Toolkit für **Discord**, **Steam** und **Rockstar Social Club** — mit
Discord-Webhook Live-Delivery und mobile-first Web-UI für iPhone.

## Features

- **Generator**: Discord / Steam / Rockstar Accounts (modular, jede Plattform = eigene Datei)
- **Token Checker**: Discord Tokens validieren (valid/invalid/locked/Nitro/Billing)
- **Mass Joiner**: Tokens auf einen Invite joinen, mit hCaptcha-Loop
- **Discord Webhook**: Live-Push jedes Accounts als Embed
- **Mobile Web-UI**: FastAPI Server + Touch-optimiertes Frontend für iPhone Safari
- TLS-Fingerprint Spoofing (`tls-client`, Chrome 124)
- 2captcha Integration (hCaptcha + reCaptcha v2)
- Proxy-Rotation (HTTP/SOCKS, mit/ohne Auth)
- mail.tm (zero-config) oder IMAP-Catchall
- Thread-Pool, Combo + JSONL Audit-Output

## Setup

```bash
git clone <repo>
cd Penisgang
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config.example.json config.json
# bearbeiten:
#   - captcha.api_key  → dein 2captcha key
#   - webhook.url      → optional, Discord Webhook URL
#   - server.auth_token → optional, schützt die Web-API
```

## CLI

### Generieren
```bash
python main.py gen --platform discord  --amount 10
python main.py gen --platform steam    --amount 5
python main.py gen --platform rockstar --amount 3
python main.py gen --platform all      --amount 30
```

### Tokens prüfen
```bash
python main.py check --file tokens.txt
python main.py check --tokens "MTI..." "OTk..."
```
Output: `output/tokens_valid.txt`, `output/tokens_invalid.txt` + Live-Console.

### Mass Join
```bash
python main.py join --invite abc123 --file tokens.txt --delay-ms 1000
python main.py join --invite https://discord.gg/abc123 --tokens "MTI..." "OTk..."
```

## iPhone Web-UI

Starte den Server auf deinem PC/Server — er druckt direkt die URL, einen
**QR-Code zum Scannen mit der iPhone-Kamera**, und kann optional einen
public HTTPS-Tunnel öffnen.

### Option 1 — Gleiches WLAN (am einfachsten)

```bash
python server.py
```
Der Output sieht so aus:
```
=========================================================
  AccGen running on  →  http://192.168.1.42:8000
=========================================================
  same WiFi as your iPhone? scan this QR with the camera:

  █▀▀▀▀▀█ ▄▀█▄█ █▀▀▀▀▀█
  █ ███ █ ██▀▀▄ █ ███ █
  …
```
**iPhone-Kamera → QR scannen → Safari öffnet die UI** → "Zum Home-Bildschirm
hinzufügen" → läuft wie eine native App.

### Option 2 — Cloudflare Tunnel (überall, nicht nur WLAN, kein Login)

```bash
# einmalig cloudflared installieren:
# macOS:    brew install cloudflared
# Windows:  winget install Cloudflare.cloudflared
# Linux:    siehe https://pkg.cloudflare.com/

python server.py --tunnel cloudflare
```
Cloudflare gibt dir eine kostenlose, zufällige `https://*.trycloudflare.com` URL
plus QR-Code. Funktioniert von überall (4G/5G, anderes WLAN, Cafe). Kein Account
nötig.

### Option 3 — ngrok (alternative)

```bash
python server.py --tunnel ngrok --ngrok-token DEIN_TOKEN
```
Braucht kostenlosen Account auf ngrok.com → dashboard → authtoken kopieren.

> **⚠ Sicherheit bei Tunneln**: Sobald deine UI public ist (Option 2/3),
> setze unbedingt `server.auth_token` in der `config.json`. Sonst kann jeder
> der die URL errät dein Tool benutzen. Im UI-Tab "Config" → Server Token
> denselben Wert eingeben.

Die UI hat 4 Tabs:
- **Generate** — Plattform wählen, Menge eingeben, klick.
- **Check** — Tokens reinpasten, valid/invalid Liste in Echtzeit.
- **Join** — Invite + Tokens, läuft mit Delay durch.
- **Config** — Webhook URL direkt vom Handy setzen/ändern.

Alle Aktionen pushen Live-Logs ins Web-UI **und** (wenn aktiviert) als Embed an
den Discord-Webhook.

> **Sicherheit**: Setze `server.auth_token` in der `config.json`, sonst kann jeder
> in deinem Netzwerk die API benutzen. Den gleichen Token im Web-UI Tab "Config"
> → "Server Token" eingeben (wird in `localStorage` gespeichert).

## Discord Webhook

In `config.json`:
```json
"webhook": {
  "enabled": true,
  "url": "https://discord.com/api/webhooks/.../...",
  "username": "AccGen"
}
```

Jeder erfolgreich generierte Account wird als farbcodierter Embed gesendet
(Discord blurple, Steam dunkelblau, Rockstar orange) mit Username, Email,
Passwort, Token, Proxy und allen Extras.

Du kannst die Webhook URL auch zur Laufzeit über die Web-UI ändern — wird in
`config.json` persistiert.

## Architektur

```
main.py                 # CLI: gen / check / join
server.py               # FastAPI mobile UI
static/                 # HTML / CSS / JS (mobile-first)
└── index.html, style.css, app.js
src/
├── account.py          # Account dataclass + combo formatter
├── output.py           # thread-safe writer + webhook fan-out
├── proxies.py          # round-robin proxy pool
├── captcha.py          # 2captcha (hCaptcha + reCaptcha v2)
├── mail.py             # mail.tm + IMAP catchall
├── names.py            # username / passwort / DOB
├── webhook.py          # Discord webhook sender
├── generators/
│   ├── base.py
│   ├── discord.py
│   ├── steam.py
│   └── rockstar.py
└── tools/
    ├── token_checker.py   # Discord token validator
    └── joiner.py          # Discord mass joiner
```

## Neue Plattform hinzufügen

1. `src/generators/<plattform>.py` anlegen, von `BaseGenerator` erben, `.generate()` implementieren
2. In `src/generators/__init__.py` ins `REGISTRY` dict eintragen
3. Sofort über CLI, Web-UI und Webhook verfügbar

## Output

```
output/
├── discord/
│   ├── discord_20260624_201500.txt    # combo
│   └── discord_20260624_201500.jsonl  # full
├── steam/
├── rockstar/
├── tokens_valid.txt
└── tokens_invalid.txt
```
