#!/usr/bin/env python3
"""
Proxy Manager — Supabase-backed proxy pool with local 24h cooldown cache.

Usage:
  proxy_manager.py --sync                  # pull all working proxies from Supabase
  proxy_manager.py --next                  # get next unused proxy URL
  proxy_manager.py --next --type residential
  proxy_manager.py --mark-used URL         # mark as used (24h cooldown)
  proxy_manager.py --pool                  # show cache stats
  proxy_manager.py --flush                 # clear used timestamps
  proxy_manager.py --add URL               # manually add proxy
  proxy_manager.py --remove URL            # manually remove proxy
"""

import argparse
import json
import os
import random
import sys
import time

TABLE = "proxy_results"
CACHE_PATH = os.path.expanduser("~/.vplink_proxy_cache.json")
CONFIG_PATH = os.path.expanduser("~/.vplink/config.json")
COOLDOWN_SECS = 86400  # 24 hours


def get_config():
    """Read Supabase credentials from env vars or ~/.vplink/config.json."""
    url = os.environ.get("SUPABASE_URL") or ""
    key = os.environ.get("SUPABASE_SERVICE_KEY") or ""
    if url and key:
        return url, key
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            cfg = json.load(f)
        url = cfg.get("supabase_url", "")
        key = cfg.get("supabase_service_key", "")
    if not url or not key:
        print("  [ERROR] Supabase credentials not found.", file=sys.stderr)
        print("  Set SUPABASE_URL and SUPABASE_SERVICE_KEY env vars", file=sys.stderr)
        print(f"  or create {CONFIG_PATH}", file=sys.stderr)
        sys.exit(1)
    return url, key


def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {"proxies": [], "used": {}, "last_sync": 0}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH) or ".", exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


# ─── Supabase API ────────────────────────────────────────────────────────

def supabase_get(table: str, params: dict = None) -> list:
    import httpx
    url, key = get_config()
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    api_url = f"{url}/rest/v1/{table}"
    r = httpx.get(api_url, headers=headers, params=params, timeout=30)
    r.raise_for_status()
    return r.json()


def fetch_proxies_from_supabase() -> list[dict]:
    rows = []
    offset = 0
    limit = 1000
    while True:
        batch = supabase_get(TABLE, {
            "select": "*",
            "e2_ok": "eq.true",
            "limit": limit,
            "offset": offset,
        })
        if not batch:
            break
        rows.extend(batch)
        offset += limit
    return rows


def _norm(p: dict) -> dict:
    url = f"http://{p['ip']}:{p['port']}"
    return {
        "url": url,
        "ip": p["ip"],
        "port": p["port"],
        "proto": p.get("proto", "http"),
        "latency_ms": p.get("latency_ms", 0) or 0,
        "speed_kbps": p.get("speed_kbps", 0) or 0,
        "type": p.get("type", ""),
        "isp": p.get("isp", ""),
        "country": p.get("country", ""),
        "city": p.get("city", ""),
        "region": p.get("region", ""),
        "vplink_ok": bool(p.get("vplink_ok")),
        "e2_ok": bool(p.get("e2_ok")),
    }


# ─── Cache Commands ──────────────────────────────────────────────────────

def cmd_sync(args):
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        print("  [!] Supabase credentials not configured in proxy_manager.py")
        sys.exit(1)
    print("  [*] Syncing from Supabase...")
    proxies = fetch_proxies_from_supabase()
    print(f"  [*] {len(proxies)} working proxies in DB")
    cache = load_cache()
    cache["proxies"] = [_norm(p) for p in proxies]
    cache["last_sync"] = time.time()
    save_cache(cache)
    print(f"  [✓] Synced {len(cache['proxies'])} proxies to local cache")


def cmd_next(args):
    cache = load_cache()
    if not cache.get("proxies"):
        print("  [!] No proxies in cache. Run --sync first.")
        sys.exit(1)
    now = time.time()
    candidates = []
    for p in cache["proxies"]:
        url = p["url"]
        last_used = cache.get("used", {}).get(url)
        if last_used and (now - last_used) < COOLDOWN_SECS:
            continue
        if args.type and p.get("type") != args.type:
            continue
        candidates.append(p)
    if not candidates:
        print("  [!] No unused proxies available.")
        sys.exit(1)
    # Sort by speed DESC, then latency ASC
    candidates.sort(key=lambda x: (-x.get("speed_kbps", 0), x.get("latency_ms", 9999)))
    pick = candidates[0]
    print(pick["url"])


def cmd_pool(args):
    cache = load_cache()
    now = time.time()
    proxies = cache.get("proxies", [])
    used = cache.get("used", {})
    total = len(proxies)
    fresh = 0
    for p in proxies:
        lu = used.get(p["url"])
        if not lu or (now - lu) >= COOLDOWN_SECS:
            fresh += 1
    res = sum(1 for p in proxies if p.get("type") == "residential")
    dc = sum(1 for p in proxies if p.get("type") == "datacenter")
    vplink = sum(1 for p in proxies if p.get("vplink_ok"))
    print(f"  Pool: {total} proxies, {fresh} fresh, {len(used)} in cooldown")
    print(f"  Residential: {res}, Datacenter: {dc}, VPLINK-verified: {vplink}")
    ls = cache.get("last_sync", 0)
    if ls:
        print(f"  Last sync: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ls))}")


def cmd_flush(args):
    cache = load_cache()
    cache["used"] = {}
    save_cache(cache)
    print("  [✓] All cooldown timestamps cleared.")


def cmd_add(args):
    url = args.add
    if "://" not in url:
        url = f"http://{url}"
    cache = load_cache()
    for p in cache["proxies"]:
        if p["url"] == url:
            print(f"  Already in cache: {url}")
            return
    rest = url.split("://", 1)[1]
    ip, port_str = rest.rsplit(":", 1)
    entry = _norm({"ip": ip, "port": int(port_str), "latency_ms": 0,
                   "speed_kbps": 0, "type": args.type or "", "vplink_ok": False, "e2_ok": True})
    cache["proxies"].append(entry)
    save_cache(cache)
    print(f"  Added: {url}")


def cmd_remove(args):
    url = args.remove
    cache = load_cache()
    cache["proxies"] = [p for p in cache["proxies"] if p["url"] != url]
    cache["used"].pop(url, None)
    save_cache(cache)
    print(f"  Removed: {url}")


def mark_used(proxy_url):
    cache = load_cache()
    cache["used"][proxy_url] = time.time()
    # Keep in pool but mark cooldown — removes from fresh selection
    save_cache(cache)


# ─── Main ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Proxy Manager — Supabase-backed IP rotation")
    parser.add_argument("--sync", action="store_true", help="Pull all working proxies from Supabase")
    parser.add_argument("--next", action="store_true", help="Get next unused proxy URL")
    parser.add_argument("--type", choices=["residential", "datacenter"], help="Preferred proxy type")
    parser.add_argument("--mark-used", metavar="URL", help="Mark proxy as used (24h cooldown)")
    parser.add_argument("--pool", action="store_true", help="Show cache pool stats")
    parser.add_argument("--flush", action="store_true", help="Clear all cooldowns")
    parser.add_argument("--add", metavar="URL", help="Add proxy to pool")
    parser.add_argument("--remove", metavar="URL", help="Remove proxy from pool")
    args = parser.parse_args()

    if args.sync:
        cmd_sync(args)
    elif args.mark_used:
        mark_used(args.mark_used)
        print(f"  Marked used: {args.mark_used}")
    elif args.pool:
        cmd_pool(args)
    elif args.flush:
        cmd_flush(args)
    elif args.add:
        cmd_add(args)
    elif args.remove:
        cmd_remove(args)
    elif args.next:
        cmd_next(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
