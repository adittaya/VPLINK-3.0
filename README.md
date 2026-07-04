# VPLink 3.0

Automated vplink.in funnel — runs views in rotation with IP rotation via Supabase-backed proxy pool, captures final destination URL.

## Quick install (one-liner)

```bash
SUPABASE_URL="https://xxxxxxx.supabase.co" \
SUPABASE_SERVICE_KEY="sb_secret_xxxxxxxxxxxxxx" \
bash -c "$(curl -fsSL https://raw.githubusercontent.com/adittaya/VPLINK-3.0/proxy-rotation/install.sh)"
```

Works on: **Ubuntu**, **Debian**, **Fedora**, **RHEL**, **Arch**, **openSUSE**, **Alpine**, **Termux** (Android).

> **First time?** Run the interactive one-liner (without env vars) — the installer will prompt for your Supabase credentials and save them permanently to `~/.vplink/config.json`:
>
> ```bash
> bash -c "$(curl -fsSL https://raw.githubusercontent.com/adittaya/VPLINK-3.0/proxy-rotation/install.sh)"
> ```

After install:

```bash
vplink3.0
```

## Credentials

VPLink 3.0 uses **Supabase** as the proxy pool backend. You need a Supabase project with the `proxy_results` table.

1. Create a free project at [supabase.com](https://supabase.com)
2. Go to **Project Settings → API** 
3. Copy your **Project URL** (SUPABASE_URL) and **service_role key** (SUPABASE_SERVICE_KEY)

The installer saves these to `~/.vplink/config.json` (chmod 600) and the proxy tools read them automatically.

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌───────────────┐
│  vplink3.0   │────▶│  proxy_manager   │────▶│  Supabase DB  │
│  (launcher)  │     │  (local cache +   │     │  (proxy pool) │
│              │◀────│   24h cooldown)   │◀────│  193 proxies  │
└──────────────┘     └──────────────────┘     └───────────────┘
       │                                              │
       ▼                                              ▼
generated_automation.js                    proxy_cleaner.py
(Playwright browser)                      (scans + tests + deletes dead proxies)
```

- **proxy_cleaner.py** — connects to Supabase, tests every proxy, deletes dead ones, updates speed/latency
- **proxy_manager.py** — syncs the clean pool from Supabase, manages 24h per-proxy cooldown, rotates per view
- Each view gets a **different proxy IP** from the pool; same IP is never reused within 24 hours

## Usage

### Interactive

```bash
vplink3.0
```

Prompts for:
- **vplink key** — the key from vplink.in URL (or paste full URL)
- **views** — how many times to run (1-50)
- **Proxy rotation** — each view gets a different verified residential proxy (default: on)
- **Clean dead proxies?** — optionally run the pool scanner/cleaner first

Each view uses a different IP; same IP never reused within 24h.

### Non-interactive (flags)

```bash
vplink3.0 --key UbpV2D --views 5
vplink3.0 --key UbpV2D --views 10 --clean   # also run cleaner
vplink3.0 --key UbpV2D --views 3 --no-proxy  # skip proxy rotation
vplink3.0 --key UbpV2D --views 2 --vnc       # enable VNC viewer
VPLINK_VNC=1 vplink3.0 --key UbpV2D --views 2  # VNC via env var
```

| Flag | Description |
|------|-------------|
| `--key KEY` | vplink key (or full URL) |
| `--views N` | number of views (1-50) |
| `--clean` | run proxy pool cleaner before sync |
| `--no-proxy` | disable proxy rotation |
| `--no-yt` | disable YouTube referral |
| `--vnc` | enable VNC viewer on port 5900 (Linux only) |

## Features

### Android Profile Rotation
Each view uses a random Android device profile from 20 pre-configured devices (Samsung Galaxy S24 Ultra, Pixel 8 Pro, OnePlus 12, Xiaomi 14, etc.). The automation emulates:
- Mobile user agent string
- Device viewport dimensions
- Device scale factor (DPR)
- Touch events (`isMobile=true`, `hasTouch=true`)

This makes each view appear to come from a different Android phone, avoiding browser fingerprinting detection.

### YouTube Referral
Each view sends the `Referer` header set to a YouTube video URL, making the traffic appear to originate from YouTube. You can provide a specific YouTube URL or use a random trending video from a built-in pool.

### VNC Auto-Detection
The launcher auto-detects any existing VNC server running on ports 5900-5905. If found, it asks whether to use the existing server or start a new one on a different port.

### Process Isolation (PID Tracking)
The launcher tracks only the processes it starts (Xvfb, x11vnc) in a PID file. Cleanup only kills tracked processes — it never kills system servers or unrelated background tasks.

## Pool management

```bash
cd ~/vplink3.0
python3 proxy_cleaner.py --stats       # view pool status
python3 proxy_cleaner.py --scan        # full scan + clean + speed test
python3 proxy_manager.py --pool        # local cache stats
python3 proxy_manager.py --flush       # reset all cooldowns
```

## Manual setup

```bash
git clone -b proxy-rotation https://github.com/adittaya/VPLINK-3.0 ~/vplink3.0
cd ~/vplink3.0
npm install
npx playwright install chromium
sudo cp vplink3.0.sh /usr/local/bin/vplink3.0
sudo chmod +x /usr/local/bin/vplink3.0

# Set up credentials
mkdir -p ~/.vplink
cat > ~/.vplink/config.json << 'EOF'
{
  "supabase_url": "https://xxxxxxx.supabase.co",
  "supabase_service_key": "sb_secret_xxxxxxxxxxxxxx"
}
EOF
chmod 600 ~/.vplink/config.json

vplink3.0
```
