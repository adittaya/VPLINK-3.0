"""Unified configuration for the browser-automation template.

Priority: environment variables > JSON config file > defaults.

Config file (XDG-compliant, single path for all languages):
    ~/.config/browser-automation/config.json   (0600)

Env vars (see .env.example):
    TARGET_URL, HEADLESS, PAGE_TIMEOUT_S, VIEWPORT_W/H,
    PROXY_URL, USER_AGENT, OUTPUT_DIR, BROWSER_BIN
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path

APP_NAME = "browser-automation"
CONFIG_DIR = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / APP_NAME
CONFIG_PATH = CONFIG_DIR / "config.json"

DEFAULTS: dict = {
    "target_url": "https://example.com",
    "headless": True,
    "page_timeout_s": 30,
    "viewport": {"width": 1366, "height": 768},
    "user_agent": "",
    "proxy_enabled": False,
    "proxy_url": "",
    "proxy_file": "",
    "output_dir": "output",
    "browser_bin": "",
}


def _ensure_dir() -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    try:
        CONFIG_DIR.chmod(0o700)
    except Exception:
        pass


def _coerce(key: str, value: str):
    if key == "headless":
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    if key in ("proxy_enabled",):
        return value.strip().lower() in ("1", "true", "yes", "y", "on")
    if key in ("page_timeout_s",):
        try:
            return int(value)
        except ValueError:
            return value
    if key in ("viewport",):
        return value  # overridden via VIEWPORT_W/H below, not raw JSON
    return value


_ENV_MAP = {
    "TARGET_URL": "target_url",
    "HEADLESS": "headless",
    "PAGE_TIMEOUT_S": "page_timeout_s",
    "USER_AGENT": "user_agent",
    "PROXY_ENABLED": "proxy_enabled",
    "PROXY_URL": "proxy_url",
    "HTTP_PROXY": "proxy_url",
    "HTTPS_PROXY": "proxy_url",
    "PROXY_FILE": "proxy_file",
    "OUTPUT_DIR": "output_dir",
    "BROWSER_BIN": "browser_bin",
    "CHROMIUM_PATH": "browser_bin",
}


def load() -> dict:
    """Load merged config: defaults < file < env."""
    _ensure_dir()
    cfg = dict(DEFAULTS)
    try:
        saved = json.loads(CONFIG_PATH.read_text("utf-8"))
        if isinstance(saved, dict):
            cfg.update(saved)
    except Exception:
        pass
    for env_key, cfg_key in _ENV_MAP.items():
        if env_key in os.environ and os.environ[env_key] != "":
            cfg[cfg_key] = _coerce(cfg_key, os.environ[env_key])
    # VIEWPORT_W/H override as a pair
    try:
        w = int(os.environ.get("VIEWPORT_W", ""))
        h = int(os.environ.get("VIEWPORT_H", ""))
        cfg["viewport"] = {"width": w, "height": h}
    except ValueError:
        pass
    # Normalise viewport shape
    vp = cfg.get("viewport") or {}
    cfg["viewport"] = {
        "width": int(vp.get("width", 1366)),
        "height": int(vp.get("height", 768)),
    }
    return cfg


def save(patch: dict) -> dict:
    """Merge *patch* into the JSON file (0600) and return merged config."""
    _ensure_dir()
    current: dict = {}
    try:
        current = json.loads(CONFIG_PATH.read_text("utf-8"))
    except Exception:
        current = {}
    merged = {**DEFAULTS, **current, **patch}
    fd, tmp = tempfile.mkstemp(dir=str(CONFIG_DIR), prefix="config.", suffix=".tmp")
    try:
        os.write(fd, json.dumps(merged, indent=2).encode("utf-8"))
        os.close(fd)
        os.chmod(tmp, 0o600)
        os.rename(tmp, str(CONFIG_PATH))
    except Exception:
        try:
            os.unlink(tmp)
        except Exception:
            pass
        raise
    return load()


def load_dotenv(dotenv_path: str | Path = ".env") -> None:
    """Minimal .env loader (no dependency). Does not override real env."""
    p = Path(dotenv_path)
    if not p.exists():
        return
    for line in p.read_text("utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("'\"")
        os.environ.setdefault(k, v)


if __name__ == "__main__":  # pragma: no cover
    import sys

    args = sys.argv[1:]
    if args[:1] == ["--get"] and len(args) == 2:
        print(load().get(args[1], ""))
    elif args[:1] == ["--check"]:
        print(json.dumps(load(), indent=2))
    else:
        print(json.dumps(load(), indent=2))
