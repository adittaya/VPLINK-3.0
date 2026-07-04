#!/usr/bin/env python3
"""
Proxy Analyser — two-tier proxy testing:
  1. httpx (fast, 100 concurrent) — filters obviously dead
  2. Playwright (per-proxy via proxy_test.js, 3 concurrent) — verifies Chromium compatibility

Usage:
  proxy_analyser.py --scan              # httpx batch (fast)
  proxy_analyser.py --scan --full       # httpx + Playwright verification
  proxy_analyser.py --test URL          # single Playwright test
  proxy_analyser.py --next              # best proxy by speed+latency
  proxy_analyser.py --pool              # cache stats
  proxy_analyser.py --clean             # remove dead from cache
"""

import argparse
import asyncio
import concurrent.futures
import json
import os
import subprocess
import sys
import time

CACHE_PATH = os.path.expanduser("~/.vplink_proxy_cache.json")
SCRIPT_DIR = os.path.dirname(os.path.realpath(__file__))
PROXY_TEST_JS = os.path.join(SCRIPT_DIR, "proxy_test.js")

HTTP_TIMEOUT = 10
CONCURRENCY = 100
PW_CONCURRENCY = 3
SPEED_TEST_URL = "http://httpbin.org/bytes/102400"

def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {"proxies": [], "used": {}, "last_sync": 0}

def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH) or ".", exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)

def test_httpx(proxy_url: str) -> dict:
    import httpx
    result = {"ok": False, "latency_ms": 0, "speed_kbps": 0, "ip": ""}
    t0 = time.time()
    try:
        with httpx.Client(proxy=proxy_url, timeout=HTTP_TIMEOUT) as c:
            r = c.get("http://ipinfo.io/json")
            latency = round((time.time() - t0) * 1000)
            if r.status_code == 200:
                data = r.json()
                result["ok"] = True
                result["latency_ms"] = latency
                result["ip"] = data.get("ip", "")
                t1 = time.time()
                try:
                    sr = c.get(SPEED_TEST_URL, timeout=15)
                    elapsed = time.time() - t1
                    if elapsed > 0 and sr.status_code == 200:
                        speed_kbps = round((len(sr.content) / 1024) / elapsed)
                        result["speed_kbps"] = speed_kbps
                except Exception:
                    pass
    except Exception:
        pass
    return result

def test_playwright(proxy_url: str) -> dict:
    result = {"ok": False, "latency_ms": 0}
    try:
        r = subprocess.run(
            ["node", PROXY_TEST_JS, proxy_url],
            capture_output=True, text=True, timeout=25
        )
        if r.returncode == 0:
            ms = r.stdout.strip()
            if ms and ms.isdigit():
                result["ok"] = True
                result["latency_ms"] = int(ms)
    except subprocess.TimeoutExpired:
        pass
    except Exception:
        pass
    return result

def cmd_scan(full: bool = False):
    cache = load_cache()
    proxies = cache.get("proxies", [])
    if not proxies:
        print("  [!] No proxies in cache. Run proxy_manager.py --sync first.")
        return

    print(f"  [*] Testing {len(proxies)} proxies...")

    # ── Pass 1: httpx (fast, concurrent) ──
    print("  [*] Pass 1: httpx check...")
    t0 = time.time()
    working = []
    dead = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        fut_to_url = {ex.submit(test_httpx, p["url"]): p for p in proxies}
        for fut in concurrent.futures.as_completed(fut_to_url):
            p = fut_to_url[fut]
            try:
                res = fut.result()
            except Exception:
                res = {"ok": False}
            if res["ok"]:
                p["latency_ms"] = res["latency_ms"]
                if res["speed_kbps"] > 0:
                    p["speed_kbps"] = res["speed_kbps"]
                working.append(p)
            else:
                dead.append(p)

    elapsed = time.time() - t0
    print(f"  [✓] Pass 1: {len(working)} working, {len(dead)} dead in {elapsed:.1f}s")

    if full and working:
        # ── Pass 2: Playwright (3 concurrent, slower but more accurate) ──
        print(f"  [*] Pass 2: Playwright verification of {len(working)} proxies ({PW_CONCURRENCY} concurrent)...")
        t0 = time.time()
        pw_working = []
        pw_dead = []
        with concurrent.futures.ThreadPoolExecutor(max_workers=PW_CONCURRENCY) as ex:
            fut_to_url = {ex.submit(test_playwright, p["url"]): p for p in working}
            for fut in concurrent.futures.as_completed(fut_to_url):
                p = fut_to_url[fut]
                try:
                    res = fut.result()
                except Exception:
                    res = {"ok": False}
                if res["ok"]:
                    p["pw_latency_ms"] = res["latency_ms"]
                    pw_working.append(p)
                else:
                    pw_dead.append(p)

        elapsed = time.time() - t0
        print(f"  [✓] Pass 2: {len(pw_working)} working, {len(pw_dead)} dead in {elapsed:.1f}s")

        # Update cache: remove both httpx-dead and PW-dead
        dead_set = {p["url"] for p in dead} | {p["url"] for p in pw_dead}
        new_proxies = [p for p in proxies if p["url"] not in dead_set]
        # Update speed/latency with PW results
        pw_map = {p["url"]: p for p in pw_working}
        for p in new_proxies:
            pw = pw_map.get(p["url"])
            if pw:
                p["latency_ms"] = pw.get("pw_latency_ms", p.get("latency_ms", 0))
                p["speed_kbps"] = pw.get("speed_kbps", p.get("speed_kbps", 0))

        cache["proxies"] = new_proxies
        save_cache(cache)
        print(f"  [✓] Cache updated: {len(new_proxies)} proxies remain, {len(dead) + len(pw_dead)} removed")
    else:
        # Pass 1 only: remove httpx-dead
        dead_set = {p["url"] for p in dead}
        new_proxies = [p for p in proxies if p["url"] not in dead_set]
        cache["proxies"] = new_proxies
        save_cache(cache)
        print(f"  [✓] Cache updated: {len(new_proxies)} proxies remain, {len(dead)} removed")
        if full is False and dead:
            print("  [i] Use --full for Playwright verification (slower, more accurate)")

def cmd_test(proxy_url: str):
    if "://" not in proxy_url:
        proxy_url = f"http://{proxy_url}"
    print(f"  [*] Testing {proxy_url} with Playwright...")
    t0 = time.time()
    res = test_playwright(proxy_url)
    elapsed = time.time() - t0
    if res["ok"]:
        print(f"  [✓] OK — {res['latency_ms']}ms (total {elapsed:.1f}s)")
    else:
        print(f"  [✗] FAILED ({elapsed:.1f}s)")

def cmd_next():
    cache = load_cache()
    proxies = cache.get("proxies", [])
    if not proxies:
        print("  [!] No proxies in cache. Run --sync or --scan first.")
        sys.exit(1)
    now = time.time()
    candidates = []
    for p in proxies:
        url = p["url"]
        last_used = cache.get("used", {}).get(url)
        if last_used and (now - last_used) < 86400:
            continue
        candidates.append(p)
    if not candidates:
        print("  [!] No unused proxies available.")
        sys.exit(1)
    # Sort by speed DESC, then latency ASC
    candidates.sort(key=lambda x: (-x.get("speed_kbps", 0), x.get("latency_ms", 9999)))
    print(candidates[0]["url"])

def cmd_pool():
    cache = load_cache()
    proxies = cache.get("proxies", [])
    used = cache.get("used", {})
    now = time.time()
    total = len(proxies)
    fresh = sum(1 for p in proxies
                if not used.get(p["url"]) or (now - used[p["url"]]) >= 86400)
    res = sum(1 for p in proxies if p.get("type") == "residential")
    dc = sum(1 for p in proxies if p.get("type") == "datacenter")
    avg_lat = 0
    lats = [p.get("latency_ms", 0) for p in proxies if p.get("latency_ms")]
    if lats:
        avg_lat = round(sum(lats) / len(lats))
    print(f"  Pool: {total} proxies, {fresh} fresh, {len(used)} in cooldown")
    print(f"  Residential: {res}, Datacenter: {dc}")
    print(f"  Avg latency: {avg_lat}ms")
    ls = cache.get("last_sync", 0)
    if ls:
        print(f"  Last sync: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(ls))}")

def cmd_clean():
    cache = load_cache()
    proxies = cache.get("proxies", [])
    if not proxies:
        print("  [!] No proxies in cache.")
        return
    print(f"  [*] Testing {len(proxies)} proxies with httpx...")
    working = []
    dead = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=CONCURRENCY) as ex:
        fut_to_url = {ex.submit(test_httpx, p["url"]): p for p in proxies}
        for fut in concurrent.futures.as_completed(fut_to_url):
            p = fut_to_url[fut]
            try:
                res = fut.result()
            except Exception:
                res = {"ok": False}
            if res["ok"]:
                working.append(p)
            else:
                dead.append(p)
    cache["proxies"] = working
    save_cache(cache)
    print(f"  [✓] Kept {len(working)}, removed {len(dead)} dead proxies")

def main():
    parser = argparse.ArgumentParser(description="Proxy Analyser — httpx + Playwright")
    parser.add_argument("--scan", action="store_true", help="Batch test all cached proxies")
    parser.add_argument("--full", action="store_true", help="Full Playwright verification (slow)")
    parser.add_argument("--test", metavar="URL", help="Test single proxy with Playwright")
    parser.add_argument("--next", action="store_true", help="Get best proxy by speed+latency")
    parser.add_argument("--pool", action="store_true", help="Show cache stats")
    parser.add_argument("--clean", action="store_true", help="Remove dead proxies from cache")
    args = parser.parse_args()

    if args.scan:
        cmd_scan(full=args.full)
    elif args.test:
        cmd_test(args.test)
    elif args.next:
        cmd_next()
    elif args.pool:
        cmd_pool()
    elif args.clean:
        cmd_clean()
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
