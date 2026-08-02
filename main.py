import asyncio
import logging
import sys
import signal
from colorama import Fore, Style, init

from config import config
from state_manager import StateManager
from x_tracker import XTracker, clean_tweet_url
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
=================================================================
""")

    # Initialize components
    state_mgr = StateManager()
    tracker = XTracker(config.target_x_username, config.nitter_instances)
    jap_client = JAPClient(config.jap_api_key, config.jap_api_url)

    if tracker._twikit.is_authenticated():
        logger.info(f"{Fore.GREEN}[TRACKER ENGINE] Direct X GraphQL (Twikit) Active — INSTANT 0-delay post detection enabled.{Style.RESET_ALL}")
    else:
        logger.info(f"{Fore.YELLOW}[TRACKER ENGINE] Public Nitter RSS Mirrors Active. Note: Public mirrors cache feeds for 5-15 mins. For instant 0-second detection, set X_AUTH_TOKEN or X_USERNAME/X_PASSWORD in .env.{Style.RESET_ALL}")

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
        logger.info(f"First-time startup detected. Seeding {len(initial_posts)} existing posts into processed_posts.db state DB...")
        for p in initial_posts:
            state_mgr.mark_processed(p['guid'])
        logger.info(f"{Fore.CYAN}[TIP] To manually force an order for the latest tweet right now, run: python trigger_latest.py{Style.RESET_ALL}")

    logger.info(f"{Fore.GREEN}Active monitoring started! Listening for NEW tweets from @{config.target_x_username}... (Press Ctrl+C to stop){Style.RESET_ALL}")

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
                    tweet_own_url = clean_tweet_url(newest.get('link', ''), config.target_x_username)

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
