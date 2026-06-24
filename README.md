# Account Generator

Modularer Multi-Plattform Account-Generator für **Discord**, **Steam** und **Rockstar Social Club**.

## Features

- Pro-Plattform Generator-Klassen (`src/generators/*.py`) — neue Plattformen einfach hinzufügbar
- TLS-Fingerprint Spoofing via `tls-client` (Chrome 124)
- hCaptcha / reCaptcha v2 Lösung über 2captcha API
- Proxy-Rotation (HTTP/SOCKS, authentifiziert oder offen)
- Disposable-Mail via mail.tm **oder** eigenes IMAP-Catchall Postfach
- Thread-Pool für parallele Generierung
- Combo-Output (`user:pass:token` o.ä.) + vollständiges JSONL Audit-Log

## Setup

```bash
git clone <repo>
cd Penisgang
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

cp config.example.json config.json
# config.json bearbeiten:
#   - captcha.api_key  → dein 2captcha key
#   - mail.provider    → "mail_tm" (kein setup) ODER "imap" (eigene domain)
#   - proxies.file     → pfad zu proxies.txt (eine zeile pro proxy)
```

### Proxy-Format (`proxies.txt`)

```
host:port
host:port:user:pass
user:pass@host:port
```

## Usage

### Interaktives Menü

```bash
python main.py
```

### CLI / Headless

```bash
python main.py --platform discord  --amount 10 --threads 5
python main.py --platform steam    --amount 5
python main.py --platform rockstar --amount 3
python main.py --platform all      --amount 30   # round-robin alle drei
```

## Output

```
output/
├── discord/
│   ├── discord_20260624_201500.txt      # combo: user:pass:token
│   └── discord_20260624_201500.jsonl    # vollständige JSON-Records
├── steam/
└── rockstar/
```

## Architektur

```
main.py
└── src/
    ├── account.py        # Account dataclass + combo formatter
    ├── output.py         # thread-safe writer
    ├── proxies.py        # round-robin proxy pool
    ├── captcha.py        # 2captcha (hCaptcha + reCaptcha v2)
    ├── mail.py           # mail.tm + IMAP catchall
    ├── names.py          # username / passwort / DOB generator
    └── generators/
        ├── base.py       # abstract BaseGenerator
        ├── discord.py    # /api/v9/auth/register
        ├── steam.py      # store.steampowered.com/join
        └── rockstar.py   # signin.rockstargames.com/signup
```

## Neue Plattform hinzufügen

1. `src/generators/<plattform>.py` anlegen, von `BaseGenerator` erben, `.generate()` implementieren
2. In `src/generators/__init__.py` zum `REGISTRY` dict hinzufügen
3. Fertig — sofort über das Menü und `--platform` verfügbar
