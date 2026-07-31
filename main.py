import asyncio
import logging
import sys
import signal
from colorama import Fore, Style, init

from config import config
from state_manager import StateManager
from x_tracker import XTracker
from link_parser import LinkParser
from jap_client import JAPClient

# Initialize colorama
init(autoreset=True)

# Configure logging format
logging.basicConfig(
    level=logging.INFO,
    format=f"{Fore.CYAN}%(asctime)s{Style.RESET_ALL} [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("MainDaemon")

running = True

def handle_exit(sig, frame):
    global running
    print(f"\n{Fore.YELLOW}[!] Shutdown requested. Stopping daemon gracefully...{Style.RESET_ALL}")
    running = False

async def main():
    global running
    
    print(f"""
{Fore.GREEN}================================================================={Style.RESET_ALL}
{Style.BRIGHT}{Fore.YELLOW}   X.COM -> JUSTANOTHERPANEL (JAP) HIGH-SPEED AUTO-ORDER BOT{Style.RESET_ALL}
{Fore.GREEN}================================================================={Style.RESET_ALL}
 Target Account   : {Fore.CYAN}@{config.target_x_username}{Style.RESET_ALL}
 Poll Interval    : {Fore.CYAN}{config.poll_interval} seconds{Style.RESET_ALL}
 Default Service  : {Fore.CYAN}ID {config.default_service_id}{Style.RESET_ALL}
 Default Quantity : {Fore.CYAN}{config.default_quantity}{Style.RESET_ALL}
 Nitter Instances : {Fore.CYAN}{len(config.nitter_instances)} mirrors configured{Style.RESET_ALL}
{Fore.GREEN}================================================================={Style.RESET_ALL}
""")

    # Initialize components
    state_mgr = StateManager()
    tracker = XTracker(config.target_x_username, config.nitter_instances)
    jap_client = JAPClient(config.jap_api_key, config.jap_api_url)

    # Validate JAP connection/balance at startup if API key is provided
    if config.jap_api_key != "YOUR_JAP_API_KEY_HERE":
        try:
            bal_res = await jap_client.get_balance()
            if "balance" in bal_res:
                logger.info(f"{Fore.GREEN}JAP Connection Verified! Current Balance: {bal_res.get('balance')} {bal_res.get('currency', 'USD')}{Style.RESET_ALL}")
            else:
                logger.warning(f"{Fore.YELLOW}JAP API Response: {bal_res}{Style.RESET_ALL}")
        except Exception as e:
            logger.error(f"{Fore.RED}Could not reach JAP API: {e}{Style.RESET_ALL}")
    else:
        logger.warning(f"{Fore.RED}JAP_API_KEY is unset (.env). Set your actual JAP API Key before running production orders!{Style.RESET_ALL}")

    # Initial warm-up poll to seed existing posts into memory if DB is empty
    logger.info(f"Performing initial scan for @{config.target_x_username}...")
    initial_posts = await tracker.fetch_latest_posts()
    
    # If starting fresh, mark existing posts as seen so we don't trigger back-orders on startup
    db_guids = state_mgr.get_all_processed_guids()
    if not db_guids and initial_posts:
        logger.info(f"First-time startup detected. Seeding {len(initial_posts)} existing posts to state DB...")
        for p in initial_posts:
            state_mgr.mark_processed(p['guid'])

    logger.info(f"{Fore.GREEN}Active monitoring started! Press Ctrl+C to stop.{Style.RESET_ALL}")

    while running:
        try:
            posts = await tracker.fetch_latest_posts()
            if posts:
                # Top post is the newest
                newest = posts[0]
                guid = newest['guid']

                if not state_mgr.is_processed(guid):
                    logger.info(f"{Fore.YELLOW}>>> NEW POST DETECTED! GUID: {guid}{Style.RESET_ALL}")
                    post_text = newest['description'] or newest['title']
                    tweet_own_url = newest.get('link', '')
                    # Convert nitter link to x.com link
                    if tweet_own_url and 'nitter' in tweet_own_url:
                        tweet_own_url = tweet_own_url.replace('nitter.net', 'x.com')
                        tweet_own_url = tweet_own_url.replace('nitter.poast.org', 'x.com')
                        tweet_own_url = tweet_own_url.replace('privacydev.net', 'x.com')
                        tweet_own_url = tweet_own_url.replace('nitter.privacydev.net', 'x.com')
                        tweet_own_url = tweet_own_url.replace('nitter.hu', 'x.com')
                        tweet_own_url = tweet_own_url.replace('nitter.cz', 'x.com')
                        tweet_own_url = tweet_own_url.replace('nitter.1d4.us', 'x.com')
                        tweet_own_url = tweet_own_url.replace('nitter.kavin.rocks', 'x.com')
                        tweet_own_url = tweet_own_url.replace('nitter.unixfox.eu', 'x.com')
                        # Remove #m anchor if present
                        tweet_own_url = tweet_own_url.split('#')[0]

                    if config.use_tweet_url:
                        # USE_TWEET_URL=true mode: order views/likes on the tweet itself
                        target_url = tweet_own_url
                        logger.info(f"Tweet URL mode: {Fore.CYAN}{target_url}{Style.RESET_ALL}")
                    else:
                        # Default mode: extract external link from tweet body
                        target_url = await LinkParser.get_first_target_url(post_text)
                        if target_url:
                            logger.info(f"External link extracted: {Fore.CYAN}{target_url}{Style.RESET_ALL}")
                        else:
                            # Fallback to tweet URL if no external link found
                            target_url = tweet_own_url
                            logger.info(f"No external link in post, using tweet URL: {Fore.CYAN}{target_url}{Style.RESET_ALL}")

                    if target_url:
                        # Determine Service ID (dynamic domain routing or default)
                        service_id = config.get_service_id_for_url(target_url)
                        logger.info(f"Routing to JAP Service ID: {Fore.CYAN}{service_id}{Style.RESET_ALL}")

                        # Trigger order on JustAnotherPanel
                        if config.jap_api_key != "YOUR_JAP_API_KEY_HERE":
                            res = await jap_client.add_order(
                                service_id=service_id,
                                link=target_url,
                                quantity=config.default_quantity
                            )
                            order_id = str(res.get("order", ""))
                            logger.info(f"{Fore.GREEN}SUCCESS! JAP Order Placed -> Order ID: {order_id} | Link: {target_url}{Style.RESET_ALL}")
                            state_mgr.mark_processed(guid, target_url, order_id, service_id)
                        else:
                            logger.warning(f"{Fore.YELLOW}[DEMO MODE] Would place order for {target_url} with service {service_id}{Style.RESET_ALL}")
                            state_mgr.mark_processed(guid, target_url, "DEMO_ORDER", service_id)
                    else:
                        logger.info("No actionable URL found in post body. Marking as processed.")
                        state_mgr.mark_processed(guid)

        except Exception as e:
            logger.error(f"Unexpected error in main loop: {e}")

        await asyncio.sleep(config.poll_interval)

if __name__ == "__main__":
    signal.signal(signal.SIGINT, handle_exit)
    signal.signal(signal.SIGTERM, handle_exit)
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
