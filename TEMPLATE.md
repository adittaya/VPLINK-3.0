# Using this repo as a template

## Option A: GitHub template / fork

1. Fork or "Use this template".
2. Delete what you don't need (`legacy` funnel, `installer/`, VNC scripts).
3. Keep `src/`, `examples/`, `tests/`, `docs/`, `.env.example`.
4. Set your `TARGET_URL` and go.

## Option B: Copy the template layer into another repo

```bash
cp -r src examples tests docs .env.example requirements.txt package.json <dest>/
cd <dest> && python3 -m pip install -r requirements.txt
python3 examples/basic.py
```

## Checklist for a new automation

- [ ] `cp .env.example .env`, set `TARGET_URL`
- [ ] `python3 examples/basic.py` saves a screenshot to `output/`
- [ ] Copy `examples/basic.py` → `my_flow.py`, add your steps
- [ ] Only if you need egress rotation: `examples/with_proxy.py` + `docs/PROXY.md`
  (static `PROXY_URL`, file pool `PROXY_FILE`, or Supabase pool)
- [ ] Add offline unit tests next to `tests/test_template.py`
- [ ] Wire CI secrets via env vars (never commit `.env` / `config.json`)

## What NOT to copy

- Hardcoded domains, test keys, Supabase hosts, API keys — all removed
  from this template; keep it that way.
- The old split config paths — use `src/config.py` only.
