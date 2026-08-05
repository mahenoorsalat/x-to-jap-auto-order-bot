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


async def process_new_posts(posts, state_mgr, config, jap_client):
    """Process each unprocessed post in the current feed and return a list of handled GUIDs."""
    handled_guids = []
    for post in posts or []:
        guid = post.get('guid') or post.get('link') or ''
        if not guid or state_mgr.is_processed(guid):
            continue

        logger.info(f"{Fore.YELLOW}>>> NEW POST DETECTED! GUID: {guid}{Style.RESET_ALL}")
        post_text = post.get('description') or post.get('title') or ''
        tweet_own_url = clean_tweet_url(post.get('link', ''), config.target_x_username)

        if config.use_tweet_url:
            target_url = tweet_own_url
            logger.info(f"Tweet URL mode: {Fore.CYAN}{target_url}{Style.RESET_ALL}")
        else:
            target_url = await LinkParser.get_first_target_url(post_text)
            if target_url:
                logger.info(f"External link extracted: {Fore.CYAN}{target_url}{Style.RESET_ALL}")
            else:
                target_url = tweet_own_url
                logger.info(f"No external link in post, using tweet URL: {Fore.CYAN}{target_url}{Style.RESET_ALL}")

        if target_url:
            service_id = config.get_service_id_for_url(target_url)
            logger.info(f"Routing to JAP Service ID: {Fore.CYAN}{service_id}{Style.RESET_ALL}")

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

        handled_guids.append(guid)

    return handled_guids


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

    # Initial warm-up poll to establish a baseline without treating all existing posts as processed.
    logger.info(f"Performing initial scan for @{config.target_x_username}...")
    initial_posts = await tracker.fetch_latest_posts()
    initial_known_guids = {p.get('guid') for p in initial_posts if p.get('guid')}

    db_guids = state_mgr.get_all_processed_guids()
    known_guids = set(db_guids) | initial_known_guids

    if not db_guids and initial_posts:
        logger.info("Initial baseline captured; new posts appearing after startup will be detected normally.")
        logger.info(f"{Fore.CYAN}[TIP] To manually force an order for the latest tweet right now, run: python trigger_latest.py{Style.RESET_ALL}")

    logger.info(f"{Fore.GREEN}Active monitoring started! Listening for NEW tweets from @{config.target_x_username}... (Press Ctrl+C to stop){Style.RESET_ALL}")

    while running:
        try:
            posts = await tracker.fetch_latest_posts()
            if posts:
                fresh_posts = []
                for post in posts:
                    guid = post.get('guid')
                    if not guid:
                        continue
                    if guid in known_guids or state_mgr.is_processed(guid):
                        continue
                    fresh_posts.append(post)

                if fresh_posts:
                    await process_new_posts(fresh_posts, state_mgr, config, jap_client)

                # Keep the seen GUID set updated so later polls only look for truly newer posts.
                known_guids.update({p.get('guid') for p in posts if p.get('guid')})

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
