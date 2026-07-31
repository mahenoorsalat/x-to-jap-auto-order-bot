"""
FULL LIVE END-TO-END TEST
1. Fetch latest tweet from @elonmusk via nitter.cz
2. Build tweet x.com URL
3. Place real JAP order (service 2098, 200 views)
4. Check order status
"""
import asyncio
import sys
sys.stdout.reconfigure(encoding='utf-8') if hasattr(sys.stdout, 'reconfigure') else None

from config import config
from x_tracker import XTracker
from jap_client import JAPClient

PASS = "[PASS]"
FAIL = "[FAIL]"
INFO = "[INFO]"

async def main():
    print("\n" + "="*60)
    print(" FULL LIVE END-TO-END TEST")
    print("="*60)

    # Step 1: Fetch posts
    print(f"\n[1] Fetching latest posts from @{config.target_x_username} via nitter.cz...")
    tracker = XTracker(config.target_x_username, config.nitter_instances)
    posts = await tracker.fetch_latest_posts(timeout=8.0)

    if not posts:
        print(f"{FAIL} Could not fetch posts - all mirrors down")
        return False

    print(f"{PASS} Got {len(posts)} posts")
    latest = posts[0]
    print(f"  Latest post title : {latest['title'][:80]}")
    print(f"  Raw link from feed: {latest['link']}")

    # Step 2: Convert nitter link -> x.com URL
    nitter_link = latest.get('link', '')
    tweet_url = nitter_link
    for mirror in [
        "nitter.cz", "nitter.net", "nitter.poast.org", "privacydev.net",
        "nitter.privacydev.net", "nitter.hu", "nitter.1d4.us",
        "nitter.kavin.rocks", "nitter.unixfox.eu", "n.sneed.eu", "nitter.moomoo.me"
    ]:
        tweet_url = tweet_url.replace(f"https://{mirror}", "https://x.com")
        tweet_url = tweet_url.replace(f"http://{mirror}", "https://x.com")
    tweet_url = tweet_url.split('#')[0].strip()

    print(f"\n[2] Converting to x.com URL...")
    print(f"  Tweet URL: {tweet_url}")

    if "x.com" not in tweet_url or "/status/" not in tweet_url:
        print(f"{FAIL} Could not build valid tweet URL from: {nitter_link}")
        return False
    print(f"{PASS} Valid tweet URL built")

    # Step 3: Place real JAP order
    print(f"\n[3] Placing JAP order...")
    print(f"  API Key : {config.jap_api_key[:8]}{'*'*20}")
    print(f"  Service : {config.default_service_id} (Twitter Tweet Views)")
    print(f"  Quantity: {config.default_quantity}")
    print(f"  Link    : {tweet_url}")

    jap = JAPClient(config.jap_api_key, config.jap_api_url)
    res = await jap.add_order(
        service_id=config.default_service_id,
        link=tweet_url,
        quantity=config.default_quantity
    )
    print(f"\n  JAP Response: {res}")

    if "order" in res:
        order_id = res["order"]
        print(f"{PASS} ORDER PLACED SUCCESSFULLY!")
        print(f"  Order ID: {order_id}")

        # Step 4: Check order status
        print(f"\n[4] Checking order status...")
        await asyncio.sleep(2)
        status = await jap.get_order_status(str(order_id))
        print(f"  Status: {status}")
        print(f"\n{'='*60}")
        print(f" RESULT: 100% WORKING - Order ID {order_id} placed on tweet:")
        print(f" {tweet_url}")
        print(f"{'='*60}\n")
        return True
    else:
        print(f"{FAIL} Order failed. Response: {res}")
        return False

asyncio.run(main())
