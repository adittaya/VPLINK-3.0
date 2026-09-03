"""Optional proxy support (provider-agnostic, off by default).

Reuses the existing project's proxy technology in generic form:
- rotation avoiding recently-used proxies (24h window)
- blacklist with 24h TTL
- fast TCP/CONNECT liveness check (Engine 1)
- optional Supabase-backed pool (Engine 1 source)

No proxy is used unless you opt in:

    PROXY_ENABLED=true PROXY_URL=http://user:pass@host:port python3 examples/basic.py
    PROXY_ENABLED=true PROXY_FILE=proxies.txt python3 examples/with_proxy.py
    PROXY_ENABLED=true SUPABASE_URL=... SUPABASE_KEY=... python3 examples/with_proxy.py

Providers (all implement ``get_proxy() -> str | None`` + ``mark_dead(proxy)``):
- EnvProxyProvider    — single static URL from PROXY_URL / HTTP_PROXY
- FileProxyProvider   — rotating list from a text file, with history + blacklist
- SupabaseProxyProvider — rotating pool from a Supabase table (optional dep: requests)

See docs/CONFIGURATION.md (Proxy section) and examples/with_proxy.py.
"""
from __future__ import annotations

import http.client
import os
import time
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

BLACKLIST_TTL_MS = 24 * 60 * 60 * 1000
HISTORY_WINDOW_MS = 24 * 60 * 60 * 1000


class ProxyProvider(Protocol):
    def get_proxy(self) -> str | None: ...
    def mark_dead(self, proxy: str) -> None: ...


def _now_ms() -> int:
    return int(time.time() * 1000)


def parse_proxy_url(url: str) -> dict | None:
    """Parse 'http://user:pass@host:port' (scheme optional) into parts."""
    url = (url or "").strip()
    if not url:
        return None
    if "://" not in url:
        url = "http://" + url
    try:
        p = urlparse(url)
        if not p.hostname or not p.port:
            return None
        return {"scheme": p.scheme or "http", "ip": p.hostname, "port": p.port, "url": url}
    except Exception:
        return None


def proxy_to_url(proxy: dict | str) -> str | None:
    if isinstance(proxy, str):
        return proxy if parse_proxy_url(proxy) else None
    if isinstance(proxy, dict):
        if "url" in proxy and parse_proxy_url(str(proxy["url"])):
            return str(proxy["url"])
        if "ip" in proxy and "port" in proxy:
            try:
                return f"http://{proxy['ip']}:{int(proxy['port'])}"
            except (ValueError, TypeError):
                return None
    return None


def tcp_check(proxy_url: str, host: str = "example.com", timeout_s: float = 3.0) -> bool:
    """Fast CONNECT liveness check (Engine 1 from proxy_rotator.py, generic host)."""
    parts = parse_proxy_url(proxy_url)
    if not parts:
        return False
    try:
        conn = http.client.HTTPConnection(parts["ip"], int(parts["port"]), timeout=timeout_s)
        conn.set_tunnel(host, 443)
        conn.request("GET", "/", headers={"Host": host})
        res = conn.getresponse()
        res.read(1024)
        conn.close()
        return 200 <= res.status < 400
    except Exception:
        return False


class Blacklist:
    """In-memory blacklist with TTL (mirrors proxy_rotator blacklist logic)."""

    def __init__(self, ttl_ms: int = BLACKLIST_TTL_MS) -> None:
        self.ttl_ms = ttl_ms
        self._entries: dict[str, int] = {}

    def add(self, proxy_url: str) -> None:
        self._entries[proxy_url] = _now_ms()

    def __contains__(self, proxy_url: object) -> bool:
        if not isinstance(proxy_url, str):
            return False
        ts = self._entries.get(proxy_url)
        if ts is None:
            return False
        if _now_ms() - ts > self.ttl_ms:
            del self._entries[proxy_url]
            return False
        return True

    def live(self) -> set[str]:
        now = _now_ms()
        dead = [k for k, ts in self._entries.items() if now - ts > self.ttl_ms]
        for k in dead:
            del self._entries[k]
        return set(self._entries)


class EnvProxyProvider:
    """Single static proxy from PROXY_URL / HTTP_PROXY / HTTPS_PROXY."""

    def __init__(self, env_var: str = "PROXY_URL") -> None:
        self.env_var = env_var

    def get_proxy(self) -> str | None:
        for key in (self.env_var, "HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"):
            val = os.environ.get(key, "").strip()
            if val and parse_proxy_url(val):
                return val
        return None

    def mark_dead(self, proxy: str) -> None:  # noqa: ARG002
        return None


class FileProxyProvider:
    """Rotating list from a text file (one URL per line, # comments allowed).

    Reuses rotation + blacklist tech from proxy_rotator.py:
    - skips blacklisted entries
    - avoids entries used within HISTORY_WINDOW_MS
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path or os.environ.get("PROXY_FILE", "proxies.txt"))
        self.blacklist = Blacklist()
        self._history: list[tuple[str, int]] = []

    def _read_all(self) -> list[str]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text("utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and parse_proxy_url(line):
                out.append(line)
        return out

    def _available(self) -> list[str]:
        now = _now_ms()
        self._history = [(u, ts) for u, ts in self._history if now - ts < HISTORY_WINDOW_MS]
        recent = {u for u, _ in self._history}
        return [u for u in self._read_all() if u not in self.blacklist and u not in recent]

    def get_proxy(self) -> str | None:
        import random

        avail = self._available() or [u for u in self._read_all() if u not in self.blacklist]
        if not avail:
            return None
        picked = random.choice(avail)
        self._history.append((picked, _now_ms()))
        return picked

    def mark_dead(self, proxy: str) -> None:
        self.blacklist.add(proxy)


class SupabaseProxyProvider:
    """Pool from a Supabase table (same technology as proxy_rotator.py).

    Env: SUPABASE_URL, SUPABASE_KEY (or SECRET), PROXY_TABLE (default
    'proxy_results'), PROXY_TIER (default 'premium'), PROXY_CHECK_URL.
    No hardcoded hosts or keys. Requires ``requests`` (lazy import).
    """

    def __init__(self) -> None:
        self.base = os.environ.get("SUPABASE_URL", "").rstrip("/")
        self.key = os.environ.get("SUPABASE_SECRET", "") or os.environ.get("SUPABASE_KEY", "")
        self.table = os.environ.get("PROXY_TABLE", "proxy_results")
        self.tier = os.environ.get("PROXY_TIER", "premium")
        self.check_url = os.environ.get("PROXY_CHECK_URL", os.environ.get("TARGET_URL", "https://example.com"))
        self.blacklist = Blacklist()
        self._history: list[tuple[str, int]] = []

    def is_configured(self) -> bool:
        return bool(self.base and self.key)

    def _fetch(self, limit: int = 200) -> list[str]:
        import requests

        field = os.environ.get("PROXY_OK_FIELD", "")
        if not field:
            field = "vplink_ok" if self.tier == "premium" else "e2_ok"
        endpoint = f"/rest/v1/{self.table}?select=ip,port&{field}=eq.true&order=latency_ms.asc&limit={limit}"
        resp = requests.get(
            self.base + endpoint,
            headers={"apikey": self.key, "Authorization": f"Bearer {self.key}"},
            timeout=25,
        )
        resp.raise_for_status()
        out = []
        for row in resp.json():
            url = proxy_to_url(f"http://{row['ip']}:{row['port']}")
            if url:
                out.append(url)
        return out

    def get_proxy(self) -> str | None:
        import random

        if not self.is_configured():
            return None
        try:
            pool = self._fetch()
        except Exception:
            return None
        now = _now_ms()
        self._history = [(u, ts) for u, ts in self._history if now - ts < HISTORY_WINDOW_MS]
        recent = {u for u, _ in self._history}
        avail = [u for u in pool if u not in self.blacklist and u not in recent]
        if not avail:
            avail = [u for u in pool if u not in self.blacklist]
        if not avail:
            return None
        picked = random.choice(avail)
        self._history.append((picked, now))
        return picked

    def mark_dead(self, proxy: str) -> None:
        self.blacklist.add(proxy)
        # Best-effort delete from the table (mirrors mark_dead in proxy_rotator.py).
        if not self.is_configured():
            return
        parts = parse_proxy_url(proxy)
        if not parts:
            return
        try:
            import requests

            requests.delete(
                f"{self.base}/rest/v1/{self.table}?ip=eq.{parts['ip']}&port=eq.{parts['port']}",
                headers={"apikey": self.key, "Authorization": f"Bearer {self.key}"},
                timeout=15,
            )
        except Exception:
            pass


def is_proxy_enabled(cfg: dict | None = None) -> bool:
    if os.environ.get("PROXY_ENABLED", "").strip().lower() in ("1", "true", "yes", "y", "on"):
        return True
    if cfg and cfg.get("proxy_enabled"):
        return True
    # Implicit opt-in: proxy details present without explicit disable.
    if os.environ.get("PROXY_DISABLED", "").strip().lower() in ("1", "true", "yes"):
        return False
    return bool(
        os.environ.get("PROXY_URL")
        or os.environ.get("PROXY_FILE")
        or (os.environ.get("SUPABASE_URL") and os.environ.get("SUPABASE_KEY"))
    )


def get_provider(cfg: dict | None = None) -> ProxyProvider | None:
    """Factory: None when disabled, else Supabase > File > Env."""
    if not is_proxy_enabled(cfg):
        return None
    sup = SupabaseProxyProvider()
    if sup.is_configured():
        return sup
    fp = os.environ.get("PROXY_FILE", "")
    if fp and Path(fp).exists():
        return FileProxyProvider(fp)
    env = EnvProxyProvider().get_proxy()
    if env:
        return EnvProxyProvider()
    # PROXY_ENABLED=true but nothing configured → explicit None (direct).
    return None


def get_proxy_url(cfg: dict | None = None) -> str | None:
    """Resolve one proxy URL or None (direct connection)."""
    if cfg and cfg.get("proxy_url") and is_proxy_enabled(cfg):
        return str(cfg["proxy_url"])
    provider = get_provider(cfg)
    return provider.get_proxy() if provider else None
