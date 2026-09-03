# Configuration

Single rule: **environment variables beat the JSON file, which beats defaults.**

## Config file

Path (same for every language in this template):

```text
~/.config/browser-automation/config.json   # mode 0600
```

Inspect / edit:

```bash
python3 src/config.py --check
python3 -c "from src.config import save; save({'target_url': 'https://example.com'})"
```

> Legacy note: the old vplink code used `~/.vplink3.0/config.json` (JS)
> and `~/.config/vplink3/config.json` (Python). The template unifies on
> `~/.config/browser-automation/config.json`. Old paths are untouched.

## Environment variables

| Var | Default | Meaning |
| --- | ------- | ------- |
| `TARGET_URL` | `https://example.com` | Page the example visits |
| `HEADLESS` | `true` | `false` for a visible browser |
| `PAGE_TIMEOUT_S` | `30` | Navigation timeout |
| `VIEWPORT_W` / `VIEWPORT_H` | `1366` / `768` | Window size |
| `USER_AGENT` | random from `src/profiles.py` | Override UA |
| `PROXY_URL` (or `HTTP_PROXY`/`HTTPS_PROXY`) | empty (direct) | e.g. `http://user:pass@host:port` |
| `PROXY_ENABLED` | `false` | `true` to opt into the proxy layer |
| `PROXY_FILE` | empty | path to rotating pool file (see `proxies.example.txt`) |
| `SUPABASE_URL` / `SUPABASE_KEY` / `SUPABASE_SECRET` | empty | Supabase pool source (no bundled defaults) |
| `PROXY_TABLE` | `proxy_results` | Supabase table name |
| `PROXY_TIER` | `premium` | pool tier selector |
| `PROXY_CHECK_URL` | `TARGET_URL` | liveness-check target |
| `OUTPUT_DIR` | `output` | Screenshots location |
| `BROWSER_BIN` (or `CHROMIUM_PATH`) | auto-detect | Explicit Chrome binary |

`.env` files are loaded by `src/config.py::load_dotenv()` (explicit call
in `examples/basic.py`) and never override real env vars.

## Proxy (optional, off by default)

Resolution order in `src/proxy.py::get_provider()`: Supabase pool >
file pool > single `PROXY_URL` > direct. All three reuse the existing
project's technology (rotation avoiding 24h-reuse, 24h-TTL blacklist,
fast CONNECT check).

```python
from src.proxy import get_provider, is_proxy_enabled

provider = get_provider(cfg)          # None when disabled/unconfigured
proxy_url = provider.get_proxy()      # str | None
provider.mark_dead(proxy_url)         # blacklist (+ best-effort DB delete for Supabase)
```

```bash
# single static proxy:
PROXY_ENABLED=true PROXY_URL=http://user:pass@host:port python3 examples/with_proxy.py
# rotating file pool:
PROXY_ENABLED=true PROXY_FILE=proxies.txt python3 examples/with_proxy.py
# Supabase pool:
PROXY_ENABLED=true SUPABASE_URL=... SUPABASE_KEY=... python3 examples/with_proxy.py
```

Full details: `docs/PROXY.md`. The legacy Supabase-backed rotators
(`legacy/proxy_rotator.py`, `legacy/proxy-rotator.js`) remain archived under
`legacy/` as reference.

## Secrets

Never commit `.env`, `config.json`, or screenshots. See `.gitignore`.
Copy `.env.example` instead. CI must inject secrets via env vars.
