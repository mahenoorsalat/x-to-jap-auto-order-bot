import asyncio
import feedparser
import httpx
import logging
import re
from typing import List, Dict, Any

logger = logging.getLogger("XTracker")

# Extended list of known working Nitter public instances
DEFAULT_NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://nitter.privacydev.net",
    "https://nitter.hu",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
    "https://n.sneed.eu",
    "https://nitter.moomoo.me",
]

def _sanitize_url(url: str) -> str:
    """Auto-fix common URL typos like missing colon in https://"""
    url = url.strip()
    # Fix https// or http// missing colon
    url = re.sub(r'^https?//', lambda m: m.group(0).replace('//', '://'), url)
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url.rstrip("/")


class XTracker:
    def __init__(self, username: str, nitter_instances: List[str]):
        self.username = username.strip("@").strip()
        # Sanitize all instance URLs to fix typos
        sanitized = [_sanitize_url(inst) for inst in nitter_instances if inst.strip()]
        # Merge with defaults so we always have fallbacks
        seen = set()
        merged = []
        for url in sanitized + DEFAULT_NITTER_INSTANCES:
            if url not in seen:
                seen.add(url)
                merged.append(url)
        self.nitter_instances = merged
        self.current_instance_idx = 0
        self._account_not_found_count = 0

    def _get_current_url(self) -> str:
        base_url = self.nitter_instances[self.current_instance_idx]
        return f"{base_url}/{self.username}/rss"

    def _rotate_instance(self):
        old_inst = self.nitter_instances[self.current_instance_idx]
        self.current_instance_idx = (self.current_instance_idx + 1) % len(self.nitter_instances)
        new_inst = self.nitter_instances[self.current_instance_idx]
        logger.warning(f"Switched Nitter instance from {old_inst} -> {new_inst}")

    async def fetch_latest_posts(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Fetch RSS feed for target account from active Nitter instance.
        - Rotates instance on 403/timeout/error
        - Stops rotating on 404 (user not found / private) and warns clearly
        Returns list of post dicts or empty list.
        """
        attempts = 0
        max_attempts = len(self.nitter_instances)
        got_404 = 0

        while attempts < max_attempts:
            target_rss_url = self._get_current_url()
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await client.get(
                        target_rss_url,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
                    )

                    if resp.status_code == 200:
                        feed = feedparser.parse(resp.text)
                        # feedparser may get a 200 but with an error inside
                        if feed.get("bozo") and not feed.entries:
                            logger.warning(f"Feed parsed but empty/invalid from {target_rss_url}")
                            self._rotate_instance()
                            attempts += 1
                            await asyncio.sleep(0.5)
                            continue

                        posts = []
                        for entry in feed.entries:
                            guid = getattr(entry, 'guid', None) or getattr(entry, 'link', None) or entry.get('title', '')
                            posts.append({
                                'guid': str(guid),
                                'title': getattr(entry, 'title', ''),
                                'description': getattr(entry, 'description', '') or getattr(entry, 'summary', ''),
                                'link': getattr(entry, 'link', ''),
                                'pubDate': getattr(entry, 'published', '')
                            })
                        self._account_not_found_count = 0  # reset on success
                        return posts

                    elif resp.status_code == 404:
                        got_404 += 1
                        logger.warning(f"[404] User '@{self.username}' not found on {self.nitter_instances[self.current_instance_idx]}")
                        # If we get 404 from 3+ instances, the account is likely private or doesn't exist
                        if got_404 >= 3:
                            logger.error(
                                f"\n{'='*60}\n"
                                f"ACCOUNT NOT FOUND: @{self.username}\n"
                                f"Possible reasons:\n"
                                f"  1. The X username is wrong - double check spelling\n"
                                f"  2. The account is PRIVATE - Nitter cannot read private accounts\n"
                                f"  3. The account was suspended or deleted\n"
                                f"Fix: Set TARGET_X_USERNAME to a PUBLIC X account username in .env\n"
                                f"{'='*60}"
                            )
                            return []

                    elif resp.status_code in (403, 429):
                        logger.warning(f"Nitter instance {target_rss_url} returned HTTP {resp.status_code} (rate limited/blocked)")
                    else:
                        logger.warning(f"Nitter instance {target_rss_url} returned HTTP {resp.status_code}")

            except httpx.TimeoutException:
                logger.debug(f"Timeout on {target_rss_url}")
            except Exception as e:
                logger.debug(f"Error requesting {target_rss_url}: {e}")

            self._rotate_instance()
            attempts += 1
            await asyncio.sleep(0.5)

        logger.error("All Nitter instances failed to respond. Will retry next poll cycle.")
        return []
