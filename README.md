# Browser-Automation Template

Generic, working starting point for browser automation — converted from the
VPLink 3.0 funnel project. Default flow visits a configurable URL, behaves
human-like, and saves a screenshot. Proxy support is **optional and off by
default**, reusing the existing rotation/blacklist tech.

## Quick start

```bash
python3 -m pip install -r requirements.txt
cp .env.example .env   # optional
python3 examples/basic.py
```

```bash
TARGET_URL=https://example.com HEADLESS=false python3 examples/basic.py
node examples/basic.js   # Playwright JS equivalent (npm install first)
```

## Optional proxy

```bash
cp proxies.example.txt proxies.txt   # one URL per line (git-ignored)
PROXY_ENABLED=true PROXY_FILE=proxies.txt python3 examples/with_proxy.py
PROXY_ENABLED=true PROXY_URL=http://user:pass@host:port python3 examples/with_proxy.py
```

Supabase pool, file pool, and static proxy all share the same
rotation + 24h-blacklist logic. Details: `docs/PROXY.md`.

## Layout

```text
src/            config, browser factory, profiles, human helpers, optional proxy
examples/       basic.py (default), with_proxy.py (optional proxy), basic.js
tests/          offline pytest suite (no browser needed)
docs/           GETTING_STARTED, CONFIGURATION, PROXY, EXAMPLES, ARCHITECTURE
.env.example    every knob, safe defaults (proxy off)
```

Docs entry point: `docs/GETTING_STARTED.md`.

## Legacy vplink code

The original site-specific funnel (`legacy/automation.py` / `legacy/automation.js`,
Supabase rotators, `legacy/installer/`, `*.sh` harnesses, research scripts) is
archived under `legacy/` as reference (see `legacy/README.md`). Use the pattern,
not the hardcoded URLs — all live keys/hosts were moved to env vars.
Mapping: `docs/ARCHITECTURE.md`.

## Tests

```bash
python3 -m pytest tests/ -q
npm test   # JS syntax check
```
