import asyncio
import feedparser
import httpx
import logging
from typing import List, Optional, Dict, Any, Tuple

logger = logging.getLogger("XTracker")

class XTracker:
    def __init__(self, username: str, nitter_instances: List[str]):
        self.username = username.strip("@").strip()
        self.nitter_instances = [inst.rstrip("/") for inst in nitter_instances]
        self.current_instance_idx = 0

    def _get_current_url(self) -> str:
        base_url = self.nitter_instances[self.current_instance_idx]
        return f"{base_url}/{self.username}/rss"

    def _rotate_instance(self):
        old_inst = self.nitter_instances[self.current_instance_idx]
        self.current_instance_idx = (self.current_instance_idx + 1) % len(self.nitter_instances)
        new_inst = self.nitter_instances[self.current_instance_idx]
        logger.warning(f"Switched Nitter instance from {old_inst} -> {new_inst}")

    async def fetch_latest_posts(self, timeout: float = 4.0) -> List[Dict[str, Any]]:
        """
        Fetch RSS feed for target account from active Nitter instance.
        Rotates instance on network/HTTP failure.
        Returns list of post dictionaries: [{'guid': ..., 'description': ..., 'link': ..., 'pubDate': ...}]
        """
        attempts = 0
        max_attempts = len(self.nitter_instances)
        
        while attempts < max_attempts:
            target_rss_url = self._get_current_url()
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await client.get(target_rss_url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
                    if resp.status_code == 200:
                        feed = feedparser.parse(resp.text)
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
                        return posts
                    else:
                        logger.warning(f"Nitter instance {target_rss_url} returned HTTP {resp.status_code}")
            except Exception as e:
                logger.debug(f"Error requesting {target_rss_url}: {e}")
                
            self._rotate_instance()
            attempts += 1
            await asyncio.sleep(0.5)

        logger.error("All Nitter instances failed to respond!")
        return []
