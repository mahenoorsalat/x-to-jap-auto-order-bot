import argparse
import asyncio
import sys
from colorama import Fore, Style, init

from config import config
from jap_client import JAPClient

init(autoreset=True)

async def run_test():
    parser = argparse.ArgumentParser(description="Test Utility for JustAnotherPanel (JAP) API")
    parser.add_argument("--balance", action="store_true", help="Check account balance")
    parser.add_argument("--services", action="store_true", help="List available services")
    parser.add_argument("--status", type=str, help="Check status of a specific Order ID")
    parser.add_argument("--order", action="store_true", help="Test placing an order")
    parser.add_argument("--service", type=str, default=config.default_service_id, help="JAP Service ID")
    parser.add_argument("--link", type=str, default="https://instagram.com/test", help="Target URL")
    parser.add_argument("--quantity", type=int, default=100, help="Order quantity")

    args = parser.parse_args()

    if config.jap_api_key == "YOUR_JAP_API_KEY_HERE":
        print(f"{Fore.RED}[Error] Please set your JAP_API_KEY in .env before running test commands!{Style.RESET_ALL}")
        sys.exit(1)

    client = JAPClient(config.jap_api_key, config.jap_api_url)

    if args.balance:
        print(f"{Fore.CYAN}Checking JAP Account Balance...{Style.RESET_ALL}")
        res = await client.get_balance()
        print(f"{Fore.GREEN}Response: {res}{Style.RESET_ALL}")

    elif args.services:
        print(f"{Fore.CYAN}Fetching JAP Services List...{Style.RESET_ALL}")
        res = await client.get_services()
        print(f"{Fore.GREEN}Fetched {len(res) if isinstance(res, list) else 'response'} items.{Style.RESET_ALL}")

    elif args.status:
        print(f"{Fore.CYAN}Checking Order Status for Order ID: {args.status}...{Style.RESET_ALL}")
        res = await client.get_order_status(args.status)
        print(f"{Fore.GREEN}Response: {res}{Style.RESET_ALL}")

    elif args.order:
        print(f"{Fore.YELLOW}Placing TEST ORDER -> Service: {args.service}, Quantity: {args.quantity}, Link: {args.link}{Style.RESET_ALL}")
        res = await client.add_order(args.service, args.link, args.quantity)
        print(f"{Fore.GREEN}Response: {res}{Style.RESET_ALL}")

    else:
        print(f"{Fore.CYAN}No specific action requested. Testing balance by default...{Style.RESET_ALL}")
        res = await client.get_balance()
        print(f"{Fore.GREEN}Response: {res}{Style.RESET_ALL}")

if __name__ == "__main__":
    asyncio.run(run_test())
