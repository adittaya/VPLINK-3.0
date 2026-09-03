# Architecture

## New template layer (generic, supported)

```text
src/
  config.py    env > JSON file > defaults; XDG path; .env loader
  browser.py   Selenium Chrome factory (lazy import, clear errors)
  profiles.py  randomised UA/viewport/locale/referrer (no site data)
  proxy.py     optional proxy: Env/File/Supabase providers + rotation/blacklist
  human.py     sleep / scroll helpers
examples/
  basic.py      default runnable flow (Python/Selenium, direct)
  with_proxy.py same flow via optional proxy layer (env/file/Supabase)
  basic.js      default runnable flow (Node/Playwright)
tests/
  test_template.py   offline unit tests (no browser needed)
docs/  GETTING_STARTED / CONFIGURATION / PROXY / EXAMPLES / ARCHITECTURE
.env.example   all knobs with safe defaults (proxy off)
```

## Legacy layer (reference, site-specific, archived under `legacy/`)

| File(s) | Stack | Role |
| ------- | ----- | ---- |
| `legacy/automation.py` | Selenium | Original funnel driver |
| `legacy/automation.js` | Playwright | Port of the funnel driver |
| `legacy/proxy_rotator.py` / `legacy/proxy-rotator.js` | Supabase | Proxy pool (now env-driven) |
| `legacy/profile_generator.py` / `legacy/profile-generator.js` | — | Original fingerprint lists |
| `legacy/config.py` / `legacy/config.js` | — | Old per-language configs (split paths) |
| `legacy/discover.js`, `legacy/cdp-explore.js`, `legacy/manual-explore.js`, `legacy/flow-recorder.js`, `legacy/recorder.js`, `legacy/analyze-*.js` | Playwright/VLM | Research & labelling tools |
| `legacy/installer/` + `legacy/install.sh` + `legacy/installer/installer.sh` | bash/Python | Heavyweight system installer |
| `legacy/vplink3.0.sh`, `legacy/vplink-desktop.sh`, `legacy/recorder.sh` | bash | Loop / VNC / record harnesses |
| `legacy/.github/workflows/ci.yml` | CI | Old distro-matrix installer tests |

Known legacy quirks (kept, documented, not re-fixed to avoid churn):

- `config.js` → `~/.vplink3.0/` vs `config.py` → `~/.config/vplink3/`
  (template uses `~/.config/browser-automation/` instead)
- duplicated Python/JS implementations of config / proxy / profile
- `package.json` was a stub; fixed in this template (see below)
- hardcoded test keys / Supabase host / NVIDIA key removed → env vars

## Packaging

- `requirements.txt`: `selenium`, `webdriver-manager`, `requests`, `urllib3`
  (+ `pytest` for tests)
- `package.json`: `playwright` + `npm run example` / `npm test` scripts
