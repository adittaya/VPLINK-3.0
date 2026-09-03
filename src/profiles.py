"""Randomised browser fingerprint profiles (generic, no site-specific data)."""
from __future__ import annotations

import random

MOBILE_UAS = [
    "Mozilla/5.0 (Linux; Android 15; Pixel 9 Pro Build/BP1A.250305.001) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.103 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 14; SM-S928B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.103 Mobile Safari/537.36",
    "Mozilla/5.0 (Linux; Android 15; Xiaomi 15 Pro) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.6533.103 Mobile Safari/537.36",
]

DESKTOP_UAS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36",
]

MOBILE_VIEWPORTS = [
    {"width": 360, "height": 780},
    {"width": 375, "height": 812},
    {"width": 390, "height": 844},
    {"width": 412, "height": 915},
]

DESKTOP_VIEWPORTS = [
    {"width": 1280, "height": 720},
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1920, "height": 1080},
]

LOCALE_PROFILES = [
    {"lang": "en-US", "timezone": "America/New_York"},
    {"lang": "en-GB", "timezone": "Europe/London"},
    {"lang": "de-DE", "timezone": "Europe/Berlin"},
    {"lang": "fr-FR", "timezone": "Europe/Paris"},
    {"lang": "hi-IN", "timezone": "Asia/Kolkata"},
    {"lang": "ja-JP", "timezone": "Asia/Tokyo"},
]

# Generic search-engine entry points (override via `referrer=` if needed).
REFERRERS = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://duckduckgo.com/",
]


def generate_profile(mobile: bool = False, referrer: str | None = None) -> dict:
    """Return a randomised fingerprint dict.

    Args:
        mobile: pick a mobile UA/viewport when True.
        referrer: optional explicit referrer URL; otherwise a random
            generic search referrer is included under ``referrer``.
    """
    ua = random.choice(MOBILE_UAS if mobile else DESKTOP_UAS)
    viewport = dict(random.choice(MOBILE_VIEWPORTS if mobile else DESKTOP_VIEWPORTS))
    locale = random.choice(LOCALE_PROFILES)
    if "Mac" in ua:
        platform = "MacIntel"
    elif "Android" in ua:
        platform = "Linux armv8l"
    elif "Linux" in ua:
        platform = "Linux x86_64"
    else:
        platform = "Win32"
    return {
        "userAgent": ua,
        "viewport": viewport,
        "locale": locale["lang"],
        "timezone": locale["timezone"],
        "platform": platform,
        "hardwareConcurrency": random.choice([2, 4, 6, 8, 12, 16]),
        "referrer": referrer if referrer is not None else random.choice(REFERRERS),
    }


if __name__ == "__main__":  # pragma: no cover
    import json

    print(json.dumps(generate_profile(), indent=2))
