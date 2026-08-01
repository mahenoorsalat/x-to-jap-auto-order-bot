"""
TRIGGER LATEST TWEET ORDER
Manually triggers a JAP order for the target account's latest tweet immediately,
bypassing the state database deduplication check. Great for testing!
"""
import asyncio
import sys
from colorama import Fore, Style, init

from config import config
from x_tracker import XTracker, clean_tweet_url
from link_parser import LinkParser
from jap_client import JAPClient

init(autoreset=True)

async def main():
    print(f"\n{Fore.CYAN}{'='*60}{Style.RESET_ALL}")
    print(f"{Fore.YELLOW}  MANUAL TRIGGER: PLACING ORDER FOR LATEST TWEET OF @{config.target_x_username}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'='*60}{Style.RESET_ALL}")

    if config.jap_api_key == "YOUR_JAP_API_KEY_HERE":
        print(f"{Fore.RED}[Error] JAP_API_KEY is not set in .env!{Style.RESET_ALL}")
        sys.exit(1)

    jap_client = JAPClient(config.jap_api_key, config.jap_api_url)
    tracker = XTracker(config.target_x_username, config.nitter_instances)

    print(f"[1] Fetching latest tweet for @{config.target_x_username}...")
    posts = await tracker.fetch_latest_posts(timeout=8.0)
    if not posts:
        print(f"{Fore.RED}[Error] Could not fetch posts. Check internet or username.{Style.RESET_ALL}")
        sys.exit(1)

    newest = posts[0]
    post_text = newest['description'] or newest['title']
    tweet_own_url = clean_tweet_url(newest.get('link', ''), config.target_x_username)

    if config.use_tweet_url:
        target_url = tweet_own_url
    else:
        ext_url = await LinkParser.get_first_target_url(post_text)
        target_url = ext_url if ext_url else tweet_own_url

    service_id = config.get_service_id_for_url(target_url)

    print(f"\n[2] Target Details:")
    print(f"  Tweet Text : {post_text[:100]}...")
    print(f"  Target URL : {target_url}")
    print(f"  Service ID : {service_id}")
    print(f"  Quantity   : {config.default_quantity}")

    print(f"\n[3] Placing JAP Order...")
    try:
        res = await jap_client.add_order(
            service_id=service_id,
            link=target_url,
            quantity=config.default_quantity
        )
        if "order" in res:
            print(f"\n{Fore.GREEN}SUCCESS! JAP Order Placed successfully!{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Order ID: {res['order']}{Style.RESET_ALL}")
            print(f"{Fore.GREEN}Link    : {target_url}{Style.RESET_ALL}")
        else:
            print(f"{Fore.RED}JAP API Response Error: {res}{Style.RESET_ALL}")
    except Exception as e:
        print(f"{Fore.RED}Error placing order: {e}{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(main())
