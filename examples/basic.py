#!/usr/bin/env python3
"""Default example: visit a page, print its title, save a screenshot.

Usage:
    pip install -r requirements.txt
    python3 examples/basic.py
    TARGET_URL=https://example.com HEADLESS=true python3 examples/basic.py
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
from src.proxy import is_proxy_enabled  # noqa: E402


def main() -> int:
    load_dotenv()
    cfg = load()
    url = os.environ.get("TARGET_URL", cfg["target_url"])
    out_dir = Path(os.environ.get("OUTPUT_DIR", cfg["output_dir"]))
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = generate_profile(mobile=False)
    print(f"[example] target   : {url}")
    print(f"[example] headless : {cfg['headless']}")
    print(f"[example] proxy    : {'on' if is_proxy_enabled(cfg) else 'off (see examples/with_proxy.py)'}")
    print(f"[example] viewport : {profile['viewport']} ua: {profile['userAgent'][:60]}...")

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
        shot = out_dir / f"example_{datetime.now():%Y%m%d-%H%M%S}.png"
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
