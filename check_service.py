import asyncio
from jap_client import JAPClient
from config import config

async def check():
    client = JAPClient(config.jap_api_key, config.jap_api_url)
    print("Fetching services list from JAP...")
    res = await client.get_services()
    if isinstance(res, list):
        print(f"Total services available: {len(res)}")
        for s in res:
            if str(s.get("service", "")) == "2098":
                print("\nSERVICE 2098 FOUND:")
                print("  Name:    ", s.get("name", "?"))
                print("  Category:", s.get("category", "?"))
                print("  Rate:    ", s.get("rate", "?"))
                print("  Min:     ", s.get("min", "?"))
                print("  Max:     ", s.get("max", "?"))
                print("  Type:    ", s.get("type", "?"))
    else:
        print("Response:", res)

asyncio.run(check())
