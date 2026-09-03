# Examples

## Default example (start here)

`examples/basic.py` — the smallest useful flow:

1. load config (`src/config.py`)
2. build a randomised profile (`src/profiles.py`)
3. create a Chrome driver (`src/browser.py`)
4. visit `TARGET_URL`, human-like scroll (`src/human.py`), screenshot to `output/`

```bash
python3 examples/basic.py
TARGET_URL=https://httpbin.org/html HEADLESS=false python3 examples/basic.py
```

`examples/basic.js` is the Playwright equivalent:

```bash
npm install && node examples/basic.js
```

## Proxy example

`examples/with_proxy.py` — same flow via the optional proxy layer
(off by default, reuses the existing rotation/blacklist tech):

```bash
python3 examples/with_proxy.py   # direct, proxy disabled
PROXY_ENABLED=true PROXY_URL=http://user:pass@host:port python3 examples/with_proxy.py
PROXY_ENABLED=true PROXY_FILE=proxies.txt python3 examples/with_proxy.py
```

See `docs/PROXY.md` for the Supabase pool and provider details.

## Copy-paste starter for your own flow

```python
from src.browser import create_driver, visit
from src.config import load, load_dotenv
from src.profiles import generate_profile

load_dotenv()
cfg = load()
cfg["target_url"] = "https://example.com"
driver = create_driver(cfg, generate_profile(mobile=True))
try:
    print(visit(driver, cfg["target_url"]))
finally:
    driver.quit()
```

## Adapting the legacy funnel code

The original `legacy/automation.py` (Selenium, ~2500 lines) and `legacy/automation.js`
(Playwright, ~2000 lines) implement a site-specific multi-step funnel.
Reuse the pattern, not the URLs:

- replace hardcoded domains/keys with `cfg["target_url"]` + argv/env
- keep `human_*` pauses and `debug_shot` screenshot helpers
- keep proxy calls behind the `ProxyProvider` interface in `src/proxy.py`

Research helpers (`legacy/discover.js`, `legacy/cdp-explore.js`, `legacy/manual-explore.js`,
`legacy/flow-recorder.js`, `legacy/recorder.js` + `legacy/recorder.sh`) show how to dump DOM /
network logs while developing a new flow.
