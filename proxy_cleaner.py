#!/usr/bin/env python3
"""
Proxy Pool Cleaner — scans all proxies in Supabase, tests them, 
deletes dead ones, updates speed/latency for working ones.

Usage:
  proxy_cleaner.py --scan          # scan + test + clean + update
  proxy_cleaner.py --scan --force  # force re-test even recently verified
  proxy_cleaner.py --stats         # quick DB stats without testing
  proxy_cleaner.py --cron          # quiet mode for cron (only output on errors)

Requires SUPABASE_URL and SUPABASE_SERVICE_KEY in environment.
"""

import asyncio
import json
import os
import sys
import time
import traceback

import httpx

TABLE = "proxy_results"
CONFIG_PATH = os.path.expanduser("~/.vplink/config.json")


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

CONCURRENCY = 100        # parallel proxy tests
TCP_TIMEOUT = 5           # seconds for TCP connect
HTTP_TIMEOUT = 10         # seconds for HTTP GET via proxy
SPEED_TEST_URL = "http://httpbin.org/bytes/102400"  # 100 KB file
SPEED_MIN_KBPS = 50
# Note: speed_kbps column not in current schema — skip speed field
MAX_AGE_HOURS = 24        # re-test proxies older than this


_CONFIG_CACHE = None

def get_config_cached():
    global _CONFIG_CACHE
    if _CONFIG_CACHE is None:
        _CONFIG_CACHE = get_config()
    return _CONFIG_CACHE


def supabase_headers():
    url, key = get_config_cached()
    return {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }, url


def fetch_all_proxies() -> list[dict]:
    headers, base_url = supabase_headers()
    rows = []
    offset = 0
    limit = 1000
    client = httpx.Client(timeout=30)
    while True:
        params = {"select": "*", "limit": limit, "offset": offset}
        r = client.get(f"{base_url}/rest/v1/{TABLE}", headers=headers, params=params)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        rows.extend(batch)
        offset += limit
    client.close()
    return rows


def delete_proxy(proxy_id: str):
    headers, base_url = supabase_headers()
    r = httpx.delete(
        f"{base_url}/rest/v1/{TABLE}",
        headers=headers,
        params={"id": f"eq.{proxy_id}"},
    )
    if r.status_code not in (200, 204):
        print(f"  [!] Delete failed for {proxy_id}: {r.status_code}")


def update_proxy(proxy_id: str, updates: dict):
    headers, base_url = supabase_headers()
    r = httpx.patch(
        f"{base_url}/rest/v1/{TABLE}",
        headers=headers,
        params={"id": f"eq.{proxy_id}"},
        json=updates,
    )
    if r.status_code not in (200, 204):
        print(f"  [!] Update failed for {proxy_id}: {r.status_code}")


async def test_proxy(ip: str, port: int) -> dict:
    proxy_url = f"http://{ip}:{port}"
    result = {"working": False, "latency_ms": 0, "speed_kbps": 0}
    t0 = time.time()
    try:
        async with httpx.AsyncClient(
            proxy=proxy_url,
            timeout=httpx.Timeout(HTTP_TIMEOUT),
        ) as client:
            resp = await client.get("http://ipinfo.io/json")
            latency = round((time.time() - t0) * 1000)
            if resp.status_code == 200:
                data = resp.json()
                result["working"] = True
                result["latency_ms"] = latency
                result["ip_out"] = data.get("ip", ip)
                result["country"] = data.get("country", "")
                result["city"] = data.get("city", "")
                result["region"] = data.get("region", "")
                result["isp"] = data.get("org", "")
                t1 = time.time()
                try:
                    speed_resp = await client.get(SPEED_TEST_URL, timeout=15)
                    elapsed = time.time() - t1
                    if elapsed > 0 and speed_resp.status_code == 200:
                        content = speed_resp.content
                        speed_kbps = round((len(content) / 1024) / elapsed)
                        result["speed_kbps"] = speed_kbps
                except Exception:
                    result["speed_kbps"] = 0
    except Exception:
        pass
    return result


async def scan_worker(proxies: list[dict], force: bool = False) -> dict:
    sem = asyncio.Semaphore(CONCURRENCY)
    now = time.time()
    stats = {"total": len(proxies), "skipped": 0, "tested": 0,
             "working": 0, "dead": 0, "deleted": 0, "updated": 0}

    def needs_test(p: dict) -> bool:
        if force:
            return True
        last_seen = p.get("last_seen")
        if not last_seen:
            return True
        try:
            age = now - datetime.fromisoformat(last_seen.replace("Z", "+00:00")).timestamp()
        except Exception:
            return True
        return age > MAX_AGE_HOURS * 3600

    async def test_one(p: dict):
        nonlocal stats
        async with sem:
            if not needs_test(p):
                stats["skipped"] += 1
                return
            stats["tested"] += 1
            ip = p["ip"]
            port = p["port"]
            result = await test_proxy(ip, port)
            if result["working"]:
                stats["working"] += 1
                updates = {
                    "e2_ok": True,
                    "latency_ms": result["latency_ms"],
                    "isp": result.get("isp", p.get("isp", "")),
                    "country": result.get("country", p.get("country", "")),
                    "city": result.get("city", p.get("city", "")),
                    "region": result.get("region", p.get("region", "")),
                    "last_seen": datetime.now(timezone.utc).isoformat(),
                }
                update_proxy(p["id"], updates)
                stats["updated"] += 1
            else:
                stats["dead"] += 1
                delete_proxy(p["id"])
                stats["deleted"] += 1

    from datetime import datetime, timezone
    tasks = [test_one(p) for p in proxies]
    await asyncio.gather(*tasks)
    return stats


def cmd_scan(force=False):
    print("  [*] Fetching all proxies from Supabase...")
    proxies = fetch_all_proxies()
    print(f"  [*] {len(proxies)} proxies in database")
    if not proxies:
        return
    print(f"  [*] Testing {len(proxies)} proxies ({CONCURRENCY} concurrent)...")
    t0 = time.time()
    stats = asyncio.run(scan_worker(proxies, force=force))
    elapsed = time.time() - t0
    print(f"  [✓] Done in {elapsed:.1f}s")
    print(f"      Total: {stats['total']}  Skipped (recent): {stats['skipped']}  "
          f"Tested: {stats['tested']}")
    print(f"      Working: {stats['working']}  Dead: {stats['dead']}  "
          f"Deleted: {stats['deleted']}  Updated: {stats['updated']}")


def cmd_stats():
    proxies = fetch_all_proxies()
    if not proxies:
        print("  [!] No proxies in database.")
        return
    vplink = sum(1 for p in proxies if p.get("vplink_ok"))
    e2 = sum(1 for p in proxies if p.get("e2_ok"))
    types = {}
    countries = set()
    for p in proxies:
        t = p.get("type", "unknown")
        types[t] = types.get(t, 0) + 1
        if p.get("country"):
            countries.add(p["country"])
    avg_latency = 0
    latencies = [p.get("latency_ms", 0) for p in proxies if p.get("latency_ms")]
    if latencies:
        avg_latency = round(sum(latencies) / len(latencies))
    print(f"  Total proxies:  {len(proxies)}")
    print(f"  e2_ok:          {e2}")
    print(f"  vplink_ok:      {vplink}")
    print(f"  Types:          {types}")
    print(f"  Countries:      {len(countries)}  {sorted(countries)}")
    print(f"  Avg latency:    {avg_latency}ms")
    print()


def cmd_cron():
    try:
        proxies = fetch_all_proxies()
        if not proxies:
            return
        stats = asyncio.run(scan_worker(proxies, force=False))
        if stats["dead"] > 0 or stats["deleted"] > 0:
            print(f"[proxy_cleaner] Cleaned: {stats['deleted']} dead, "
                  f"{stats['updated']} updated of {stats['tested']} tested")
    except Exception as e:
        print(f"[proxy_cleaner] ERROR: {e}", file=sys.stderr)


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Proxy Pool Cleaner")
    parser.add_argument("--scan", action="store_true", help="Scan, test, clean, update")
    parser.add_argument("--force", action="store_true", help="Force re-test all proxies")
    parser.add_argument("--stats", action="store_true", help="Quick DB stats")
    parser.add_argument("--cron", action="store_true", help="Quiet cron mode")
    args = parser.parse_args()

    if args.scan:
        cmd_scan(force=args.force)
    elif args.stats:
        cmd_stats()
    elif args.cron:
        cmd_cron()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
