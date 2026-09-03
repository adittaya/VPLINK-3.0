"""Selenium Chrome factory for the template.

Features:
- headless / headful via config
- custom UA + viewport + locale from a profile dict
- optional PROXY_URL support
- webdriver-manager for driver resolution, with system chromedriver fallback

Selenium is imported lazily so unit tests run without a browser installed.
"""
from __future__ import annotations

import os
import shutil
from typing import Any


def detect_chrome_binary(hint: str = "") -> str | None:
    if hint and os.path.exists(hint):
        return hint
    for cand in (
        os.environ.get("BROWSER_BIN", ""),
        os.environ.get("CHROMIUM_PATH", ""),
        "/usr/bin/google-chrome",
        "/usr/bin/google-chrome-stable",
        "/usr/bin/chromium",
        "/usr/bin/chromium-browser",
        "/opt/google/chrome/chrome",
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ):
        if cand and os.path.exists(cand):
            return cand
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        found = shutil.which(name)
        if found:
            return found
    return None


def build_options(cfg: dict, profile: dict | None = None):
    from selenium.webdriver.chrome.options import Options

    opts = Options()
    profile = profile or {}
    if cfg.get("headless", True):
        opts.add_argument("--headless=new")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-dev-shm-usage")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    vp = (profile.get("viewport") if profile else None) or cfg.get("viewport", {})
    w, h = int(vp.get("width", 1366)), int(vp.get("height", 768))
    opts.add_argument(f"--window-size={w},{h}")
    ua = (profile.get("userAgent") if profile else "") or cfg.get("user_agent", "")
    if ua:
        opts.add_argument(f"--user-agent={ua}")
    lang = (profile.get("locale") if profile else "") or "en-US"
    opts.add_argument(f"--lang={lang}")
    proxy = cfg.get("proxy_url", "")
    if not proxy:
        # Optional proxy: resolve via provider (env/file/Supabase), off by default.
        try:
            from src.proxy import get_proxy_url as _resolve_proxy

            proxy = _resolve_proxy(cfg) or ""
        except Exception:
            proxy = ""
    if proxy:
        opts.add_argument(f"--proxy-server={proxy}")
    binary = detect_chrome_binary(str(cfg.get("browser_bin", "")))
    if binary:
        opts.binary_location = binary
    return opts


def create_driver(cfg: dict, profile: dict | None = None) -> Any:
    """Create a Selenium Chrome driver. Raises RuntimeError with a clear message."""
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.service import Service
    except ImportError as exc:
        raise RuntimeError(
            "selenium is not installed. Run: pip install -r requirements.txt"
        ) from exc

    opts = build_options(cfg, profile)
    timeout = int(cfg.get("page_timeout_s", 30))

    # Prefer webdriver-manager, fall back to system chromedriver.
    try:
        from webdriver_manager.chrome import ChromeDriverManager

        service = Service(ChromeDriverManager().install())
    except Exception:
        chromedriver = shutil.which("chromedriver") or "/usr/bin/chromedriver"
        service = Service(chromedriver)

    try:
        driver = webdriver.Chrome(service=service, options=opts)
    except Exception as exc:
        raise RuntimeError(
            f"Could not start Chrome ({exc}). "
            "Install Chrome/Chromium 120+ and check BROWSER_BIN if needed."
        ) from exc
    driver.set_page_load_timeout(timeout)
    return driver


def visit(driver, url: str, timeout_s: int = 30) -> str:
    """Navigate to *url* and return the page title."""
    driver.set_page_load_timeout(timeout_s)
    driver.get(url)
    return driver.title or ""
