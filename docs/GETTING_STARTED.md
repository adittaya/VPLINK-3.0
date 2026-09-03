# Getting started

Minimal path from clone to first screenshot (under 5 minutes).

## 1. Prerequisites

- Python 3.10+
- Chrome or Chromium 120+ (only needed to actually drive a browser;
  unit tests run without it)
- Node 18+ (only for the optional JS example)

## 2. Install

```bash
git clone <your-repo-url> browser-automation
cd browser-automation
python3 -m pip install -r requirements.txt
cp .env.example .env   # optional
```

JS example only:

```bash
npm install
```

## 3. Run the default example

```bash
python3 examples/basic.py
# custom target / headful:
TARGET_URL=https://example.com HEADLESS=false python3 examples/basic.py
```

Expected output:

```text
[example] target   : https://example.com
[example] headless : True
[example] title    : 'Example Domain'
[example] screenshot: output/example_YYYYMMDD-HHMMSS.png
```

If no browser is installed you get a clear `SKIP (no browser)` message
instead of a traceback.

JS equivalent:

```bash
node examples/basic.js
```

## 4. Optional proxy

Proxy is off by default. When you need it:

```bash
cp proxies.example.txt proxies.txt   # add entries (git-ignored)
PROXY_ENABLED=true PROXY_FILE=proxies.txt python3 examples/with_proxy.py
```

## 5. Next steps

- `docs/CONFIGURATION.md` — env vars, config file, proxy setup
- `docs/PROXY.md` — optional proxy providers (env/file/Supabase)
- `docs/EXAMPLES.md` — what to copy for your own flow
- `docs/ARCHITECTURE.md` — where the legacy vplink code lives
- `TEMPLATE.md` — how to reuse this repo as a template
