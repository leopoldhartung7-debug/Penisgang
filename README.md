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

1. Auf deinem PC / Server starten:
   ```bash
   python server.py
   ```
2. Lokale IP rausfinden (z.B. `192.168.1.42`).
3. Auf dem iPhone **Safari öffnen** → `http://192.168.1.42:8000`
4. (Optional) "Zum Home-Bildschirm hinzufügen" — läuft dann wie eine App.

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
