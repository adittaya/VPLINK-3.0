# Legacy archive (VPLink 3.0)

Site-specific VPLink funnel code, archived as reference. Not part of the
template — the supported surface is `../src/`, `../examples/`, `../docs/`.

## Contents

- `automation.py` / `automation.js` — original funnel drivers
- `proxy_rotator.py` / `proxy-rotator.js` — Supabase-backed proxy pool
  (technology reused generically in `../src/proxy.py`)
- `profile_generator.py` / `profile-generator.js` — original fingerprints
- `config.py` / `config.js` — old per-language configs (split paths;
  template uses `../src/config.py` instead)
- `discover.js`, `cdp-explore.js`, `manual-explore.js`, `flow-recorder.js`,
  `recorder.js`, `analyze-*.js` — research / labelling tools
- `installer/` + `install.sh` + `installer/installer.sh` — system installer
  (`python3 -m installer verify|doctor|status` run from this directory)
- `vplink3.0.sh`, `vplink-desktop.sh`, `recorder.sh` — loop / VNC harnesses
- `.github/` — original distro-matrix CI for the installer
- `test_run.log`, `package-lock.json` — historical run log / stale lockfile

## Running legacy code

Run from this directory so sibling-relative imports/paths resolve:

```bash
cd legacy
python3 -B -m installer verify
bash installer/installer.sh help
```

Secrets (Supabase host/keys, test keys, API keys) were replaced with env
vars (`SUPABASE_URL`, `PROXY_CHECK_URL`, `FLOW_KEY`, `NVIDIA_API_KEY`, …).
