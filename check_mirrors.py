import asyncio
import httpx
import sys

# Fix Windows cp1252 encoding for special characters
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None


MIRRORS = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://privacydev.net",
    "https://nitter.privacydev.net",
    "https://nitter.hu",
    "https://nitter.cz",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
    "https://n.sneed.eu",
    "https://nitter.moomoo.me",
]

TEST_USER = "elonmusk"

async def check_mirror(mirror: str) -> tuple:
    url = f"{mirror}/{TEST_USER}/rss"
    try:
        async with httpx.AsyncClient(timeout=6.0, follow_redirects=True) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            })
        if resp.status_code == 200 and len(resp.text) > 500:
            return (mirror, "[WORKING]", resp.status_code)
        else:
            return (mirror, f"[FAIL] HTTP {resp.status_code}", resp.status_code)
    except Exception as e:
        return (mirror, f"[FAIL] {str(e)[:40]}", 0)

async def main():
    print(f"\nTesting {len(MIRRORS)} Nitter mirrors for @{TEST_USER}...\n")
    tasks = [check_mirror(m) for m in MIRRORS]
    results = await asyncio.gather(*tasks)

    working = []
    for mirror, status, code in sorted(results, key=lambda x: 0 if "WORKING" in x[1] else 1):
        print(f"  {status:45s} {mirror}")
        if "WORKING" in status:
            working.append(mirror)

    print(f"\n{'='*60}")
    print(f"Working mirrors: {len(working)}/{len(MIRRORS)}")
    if working:
        print(f"Best mirror right now: {working[0]}")
    else:
        print("ALL MIRRORS DOWN - Nitter is fully rate-limited right now")
        print("Set X_USERNAME, X_EMAIL, X_PASSWORD in .env to enable Twikit fallback")
    print('='*60)
    return working

asyncio.run(main())

