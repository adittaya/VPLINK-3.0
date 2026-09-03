#!/usr/bin/env python3
"""Proxy example: same flow as basic.py but through the optional proxy layer.

Opt-in only — with no proxy env vars this runs direct, like basic.py.

Usage:
    # direct (proxy off):
    python3 examples/with_proxy.py
    # single static proxy:
    PROXY_ENABLED=true PROXY_URL=http://user:pass@host:port python3 examples/with_proxy.py
    # rotating file pool (one URL per line):
    PROXY_ENABLED=true PROXY_FILE=proxies.txt python3 examples/with_proxy.py
    # Supabase pool (same tech as proxy_rotator.py, now env-driven):
    PROXY_ENABLED=true SUPABASE_URL=https://xyz.supabase.co SUPABASE_KEY=... \
        python3 examples/with_proxy.py
"""
import os
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.browser import create_driver, visit  # noqa: E402
from src.config import load, load_dotenv  # noqa: E402
from src.human import human_scroll  # noqa: E402
from src.profiles import generate_profile  # noqa: E402
from src.proxy import get_provider, is_proxy_enabled  # noqa: E402


def main() -> int:
    load_dotenv()
    cfg = load()
    url = os.environ.get("TARGET_URL", cfg["target_url"])
    out_dir = Path(os.environ.get("OUTPUT_DIR", cfg["output_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)

    provider = get_provider(cfg)
    if not is_proxy_enabled(cfg):
        print("[proxy] disabled — direct connection")
    elif provider is None:
        print("[proxy] enabled but nothing configured — direct connection")
    else:
        print(f"[proxy] provider : {type(provider).__name__}")
        picked = provider.get_proxy()
        if picked:
            # Mask credentials when logging.
            masked = picked
            try:
                from urllib.parse import urlparse

                p = urlparse(picked if "://" in picked else "http://" + picked)
                if "@" in picked:
                    masked = f"{p.scheme}://***@{p.hostname}:{p.port}"
            except Exception:
                pass
            print(f"[proxy] using    : {masked}")
            cfg["proxy_url"] = picked
        else:
            print("[proxy] pool empty — direct connection")

    profile = generate_profile(mobile=False)
    print(f"[example] target   : {url}")

    try:
        driver = create_driver(cfg, profile)
    except RuntimeError as exc:
        print(f"[example] SKIP (no browser): {exc}")
        return 2
    try:
        title = visit(driver, url, timeout_s=int(cfg["page_timeout_s"]))
        print(f"[example] title    : {title!r}")
        try:
            human_scroll(driver)
        except Exception:
            pass
        shot = out_dir / f"proxy_{datetime.now():%Y%m%d-%H%M%S}.png"
        driver.save_screenshot(str(shot))
        print(f"[example] screenshot: {shot}")
        return 0
    finally:
        try:
            driver.quit()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
