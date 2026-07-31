"""
FULL LIVE END-TO-END TEST
1. Fetch latest tweet from target account via XTracker (multi-engine)
2. Build canonical x.com tweet URL via clean_tweet_url
3. Verify JAP API connection & balance
"""
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

from config import config
from x_tracker import XTracker, clean_tweet_url
from jap_client import JAPClient

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

async def main():
    print("\n" + "="*60)
    print(" FULL LIVE END-TO-END SYSTEM DIAGNOSTIC")
    print("="*60)

    # Step 1: Check JAP Balance
    print(f"\n[1] Checking JAP API connection & balance...")
    jap = JAPClient(config.jap_api_key, config.jap_api_url)
    try:
        bal_res = await jap.get_balance()
        if "balance" in bal_res:
            print(f"{PASS} JAP Connection Verified! Balance: {bal_res['balance']} {bal_res.get('currency', 'USD')}")
        else:
            print(f"{FAIL} JAP API error: {bal_res}")
            return False
    except Exception as e:
        print(f"{FAIL} JAP API connection failed: {e}")
        return False

    # Step 2: Fetch posts via multi-engine tracker
    target_user = config.target_x_username
    print(f"\n[2] Fetching latest posts from @{target_user} via multi-engine tracker...")
    tracker = XTracker(target_user, config.nitter_instances)
    posts = await tracker.fetch_latest_posts(timeout=8.0)

    if not posts:
        print(f"{FAIL} Could not fetch posts - all tracking engines unavailable")
        return False

    print(f"{PASS} Got {len(posts)} posts for @{target_user}")
    latest = posts[0]
    print(f"  Latest post title : {latest['title'][:80]}")
    print(f"  Raw link from feed: {latest['link']}")

    # Step 3: Convert to clean canonical x.com URL
    tweet_url = clean_tweet_url(latest.get('link', ''), target_user)
    print(f"\n[3] Converting to canonical x.com URL...")
    print(f"  Clean Tweet URL: {tweet_url}")

    if "x.com" not in tweet_url or "/status/" not in tweet_url:
        print(f"{FAIL} Could not build valid tweet URL from: {latest.get('link', '')}")
        return False
    print(f"{PASS} Valid canonical tweet URL built: {tweet_url}")

    print(f"\n{'='*60}")
    print(f" RESULT: 100% SYSTEM VERIFIED & READY FOR 24/7 OPERATION")
    print(f" Target Account : @{target_user}")
    print(f" Latest Tweet   : {tweet_url}")
    print(f" JAP Balance    : {bal_res.get('balance')} USD")
    print(f"{'='*60}\n")
    return True

if __name__ == "__main__":
    asyncio.run(main())
