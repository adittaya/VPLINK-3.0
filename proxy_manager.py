#!/usr/bin/env python3
"""
Proxy Manager — orchestrates 3 engines + local cooldown cache.
Usage:
  proxy_manager.py --next                    # get next unused proxy
  proxy_manager.py --next --type residential  # only residential
  proxy_manager.py --mark-used http://ip:port # mark as used (24h cooldown)
  proxy_manager.py --pool                    # show cache stats
  proxy_manager.py --flush                   # clear used timestamps
"""

import argparse
import json
import os
import random
import subprocess
import sys
import time

HUNTER_DIR = os.environ.get(
    "PROXY_HUNTER_DIR",
    os.path.expanduser("~/vplink-proxy-hunter"),
)
CACHE_PATH = os.path.expanduser("~/.vplink_proxy_cache.json")
COOLDOWN_SECS = 86400  # 24 hours


def load_cache():
    if os.path.exists(CACHE_PATH):
        with open(CACHE_PATH) as f:
            return json.load(f)
    return {"proxies": [], "used": {}}


def save_cache(cache):
    os.makedirs(os.path.dirname(CACHE_PATH) or ".", exist_ok=True)
    with open(CACHE_PATH, "w") as f:
        json.dump(cache, f, indent=2)


def mark_used(proxy_url):
    cache = load_cache()
    cache["used"][proxy_url] = time.time()
    # Also remove from available pool
    cache["proxies"] = [p for p in cache["proxies"] if p.get("url") != proxy_url]
    save_cache(cache)
    print(f"  Marked used: {proxy_url}")


def get_unused(cache, pref_type=None):
    now = time.time()
    candidates = []
    for p in cache["proxies"]:
        url = p["url"]
        # Skip if used within cooldown
        last_used = cache.get("used", {}).get(url)
        if last_used and (now - last_used) < COOLDOWN_SECS:
            continue
        if pref_type and p.get("type") != pref_type:
            continue
        candidates.append(p)

    if not candidates:
        return None

    # Pick fastest
    candidates.sort(key=lambda x: x.get("latency", 9999))
    return candidates[0]


def run_hunter():
    """Engine 1: scrape public proxy lists, find residential proxies."""
    print("  Engine 1: proxy_hunter — scraping lists...")
    sys.stdout.flush()
    result_file = "/tmp/opencode/proxy_hunt_result.txt"

    # Clear previous result
    os.makedirs("/tmp/opencode", exist_ok=True)
    if os.path.exists(result_file):
        os.remove(result_file)

    script = os.path.join(HUNTER_DIR, "proxy_hunter.py")
    if not os.path.exists(script):
        print(f"  [!] proxy_hunter.py not found at {script}")
        return None

    # Run hunter with a timeout (30s max)
    try:
        subprocess.run(
            [sys.executable, script],
            timeout=30,
            cwd=HUNTER_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        print(f"  [!] hunter error: {e}")
        return None

    if os.path.exists(result_file):
        with open(result_file) as f:
            url = f.read().strip()
        if url:
            print(f"  ✅ Hunter found: {url}")
            return url

    # Fallback: parse results from hunter output — hunter writes to self.results
    # Instead, try the proxy_pull as secondary engine
    return None


def run_finder():
    """Engine 2: brute force random IPs, TCP scan, residential detection."""
    print("  Engine 2: proxy_finder — brute forcing IPs...")
    sys.stdout.flush()
    result_file = "/tmp/opencode/proxy_finder_result.txt"

    os.makedirs("/tmp/opencode", exist_ok=True)
    if os.path.exists(result_file):
        os.remove(result_file)

    script = os.path.join(HUNTER_DIR, "proxy_finder.py")
    if not os.path.exists(script):
        print(f"  [!] proxy_finder.py not found at {script}")
        return None

    # Finder runs until 5 verified found or interrupted. Give it 45s, then check if at least 1 found.
    try:
        proc = subprocess.Popen(
            [sys.executable, script],
            cwd=HUNTER_DIR,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # Check every 5s for a result
        for _ in range(18):  # 90s total
            time.sleep(5)
            if os.path.exists(result_file):
                with open(result_file) as f:
                    url = f.read().strip()
                if url:
                    proc.kill()
                    print(f"  ✅ Finder found: {url}")
                    return url
        proc.kill()
    except Exception as e:
        print(f"  [!] finder error: {e}")
        return None
    return None


def run_pull(pref_type=None):
    """Engine 3: pull from Supabase database."""
    script = os.path.join(HUNTER_DIR, "proxy_pull.py")
    if not os.path.exists(script):
        print(f"  [!] proxy_pull.py not found at {script}")
        return None

    # First check if there are any VPLINK-verified proxies
    cmd = [sys.executable, script, "--vplink", "--limit", "5", "--random", "--export", "plain"]
    if pref_type:
        cmd = [sys.executable, script, "--type", pref_type, "--limit", "5", "--random", "--export", "plain"]

    print(f"  Engine 3: proxy_pull — querying Supabase...")
    sys.stdout.flush()
    try:
        result = subprocess.run(
            cmd,
            cwd=HUNTER_DIR,
            capture_output=True,
            text=True,
            timeout=15,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        if lines:
            url = lines[0]
            # Convert proto://ip:port format
            if "://" not in url:
                url = f"http://{url}"
            print(f"  ✅ Pull found: {url}")
            return url
    except subprocess.TimeoutExpired:
        pass
    except Exception as e:
        print(f"  [!] pull error: {e}")

    return None


def fetch_proxy(pref_type=None):
    """Try all 3 engines until we find a working proxy."""
    result = None

    # Engine 3 first: fastest (already in DB)
    result = run_pull(pref_type)
    if result:
        return result

    # Engine 1: scrape public lists
    result = run_hunter()
    if result:
        return result

    # Engine 2: brute force (slow but thorough)
    result = run_finder()
    if result:
        return result

    return None


def proxy_to_dict(proxy_url):
    """Parse proxy://ip:port into dict."""
    proto = "http"
    rest = proxy_url
    if "://" in proxy_url:
        proto, rest = proxy_url.split("://", 1)
    ip_port = rest
    ip = port = None
    if ":" in ip_port:
        ip, port_str = ip_port.rsplit(":", 1)
        try:
            port = int(port_str)
        except ValueError:
            port = None
    if not ip or not port:
        return None
    return {"url": proxy_url, "proto": proto, "ip": ip, "port": port, "latency": 0, "type": "", "added": time.time()}


def add_to_pool(proxy_url):
    cache = load_cache()
    p = proxy_to_dict(proxy_url)
    if not p:
        return
    # Deduplicate
    cache["proxies"] = [x for x in cache["proxies"] if x["url"] != proxy_url]
    cache["proxies"].append(p)
    save_cache(cache)


def cmd_next(args):
    pref_type = args.type
    cache = load_cache()
    p = get_unused(cache, pref_type)

    if p:
        print(p["url"])
        return

    print("  No unused proxies in cache. Running engines...")
    sys.stdout.flush()
    url = fetch_proxy(pref_type)
    if url:
        add_to_pool(url)
        # Mark as used since we're consuming it now
        print(url)
    else:
        print("  No proxy found from any engine.")
        sys.exit(1)


def cmd_pool(args):
    cache = load_cache()
    now = time.time()
    total = len(cache.get("proxies", []))
    used_count = len(cache.get("used", {}))
    fresh = 0
    for p in cache.get("proxies", []):
        last_used = cache.get("used", {}).get(p["url"])
        if not last_used or (now - last_used) >= COOLDOWN_SECS:
            fresh += 1
    print(f"  Pool: {total} proxies, {fresh} fresh, {used_count} in cooldown")


def cmd_flush(args):
    cache = load_cache()
    cache["used"] = {}
    save_cache(cache)
    print("  All cooldown timestamps cleared.")


def main():
    parser = argparse.ArgumentParser(description="Proxy Manager — IP rotation for VPLink")
    parser.add_argument("--next", action="store_true", help="Get next unused proxy URL")
    parser.add_argument("--type", choices=["residential", "datacenter"], help="Preferred proxy type")
    parser.add_argument("--mark-used", metavar="URL", help="Mark proxy URL as used (24h cooldown)")
    parser.add_argument("--pool", action="store_true", help="Show cache pool stats")
    parser.add_argument("--flush", action="store_true", help="Clear all cooldown timestamps")
    args = parser.parse_args()

    if args.mark_used:
        mark_used(args.mark_used)
    elif args.pool:
        cmd_pool(args)
    elif args.flush:
        cmd_flush(args)
    elif args.next:
        cmd_next(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
