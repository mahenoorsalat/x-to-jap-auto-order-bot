import asyncio
import feedparser
import httpx
import logging
import re
import os
from typing import List, Dict, Any, Optional

logger = logging.getLogger("XTracker")

# Extended list of known working Nitter public instances
DEFAULT_NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://privacydev.net",
    "https://nitter.privacydev.net",
    "https://nitter.hu",
    "https://nitter.1d4.us",
    "https://nitter.kavin.rocks",
    "https://nitter.unixfox.eu",
    "https://n.sneed.eu",
    "https://nitter.moomoo.me",
    "https://nitter.cz",
]


def _sanitize_url(url: str) -> str:
    """Auto-fix common URL typos like missing colon in https://"""
    url = url.strip()
    # Fix https// or http// missing colon
    url = re.sub(r'^https?//', lambda m: m.group(0).replace('//', '://'), url)
    if not url.startswith("http://") and not url.startswith("https://"):
        url = "https://" + url
    return url.rstrip("/")


class NitterEngine:
    """Fetches X posts via public Nitter RSS mirrors."""

    def __init__(self, username: str, instances: List[str]):
        self.username = username
        sanitized = [_sanitize_url(u) for u in instances if u.strip()]
        seen, merged = set(), []
        for url in sanitized + DEFAULT_NITTER_INSTANCES:
            if url not in seen:
                seen.add(url)
                merged.append(url)
        self.instances = merged
        self.idx = 0

    def _current_url(self) -> str:
        return f"{self.instances[self.idx]}/{self.username}/rss"

    def _rotate(self):
        old = self.instances[self.idx]
        self.idx = (self.idx + 1) % len(self.instances)
        logger.warning(f"Switched Nitter instance from {old} -> {self.instances[self.idx]}")

    async def fetch(self, timeout: float = 5.0) -> Optional[List[Dict[str, Any]]]:
        """
        Returns list of posts, empty list on 404/private, or None if all rate-limited.
        None means 'try another engine', [] means 'account not found/private'.
        """
        got_404 = 0
        for _ in range(len(self.instances)):
            url = self._current_url()
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await client.get(url, headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    })

                if resp.status_code == 200:
                    feed = feedparser.parse(resp.text)
                    if not feed.entries:
                        logger.warning(f"Feed returned 0 entries from {url}, rotating...")
                        self._rotate()
                        await asyncio.sleep(0.5)
                        continue

                    posts = []
                    for entry in feed.entries:
                        guid = getattr(entry, 'guid', None) or getattr(entry, 'link', None) or ''
                        posts.append({
                            'guid': str(guid),
                            'title': getattr(entry, 'title', ''),
                            'description': getattr(entry, 'description', '') or getattr(entry, 'summary', ''),
                            'link': getattr(entry, 'link', ''),
                            'pubDate': getattr(entry, 'published', '')
                        })
                    logger.debug(f"Nitter: {len(posts)} posts from {self.instances[self.idx]}")
                    return posts

                elif resp.status_code == 404:
                    got_404 += 1
                    logger.warning(f"[404] @{self.username} not found on {self.instances[self.idx]}")
                    if got_404 >= 3:
                        logger.error(
                            f"\n{'='*60}\n"
                            f"ACCOUNT NOT FOUND: @{self.username}\n"
                            f"Reasons: wrong username, private account, or suspended.\n"
                            f"Fix: Set TARGET_X_USERNAME to a PUBLIC X account in .env\n"
                            f"{'='*60}"
                        )
                        return []
                else:
                    logger.warning(f"Nitter {url} returned HTTP {resp.status_code}")

            except httpx.TimeoutException:
                logger.debug(f"Timeout: {url}")
            except Exception as e:
                logger.debug(f"Error: {url}: {e}")

            self._rotate()
            await asyncio.sleep(0.5)

        logger.warning("All Nitter mirrors rate-limited. Will retry next cycle.")
        return None  # None = all rate-limited, not account error


class TwikitEngine:
    """
    Fetches X posts via Twikit (X guest API / cookie-based).
    Requires: pip install twikit
    Optional: set X_USERNAME, X_EMAIL, X_PASSWORD in .env for authenticated access.
    Falls back to guest token mode if no credentials provided.
    """

    def __init__(self, username: str):
        self.username = username
        self._client = None
        self._available = False
        try:
            from twikit import Client  # noqa
            self._available = True
        except ImportError:
            logger.debug("Twikit not installed — skipping Twikit engine")

    async def _init_client(self):
        if not self._available or self._client is not None:
            return
        try:
            from twikit import Client
            client = Client("en-US")
            x_user = os.getenv("X_USERNAME", "")
            x_email = os.getenv("X_EMAIL", "")
            x_pass = os.getenv("X_PASSWORD", "")
            cookies_file = "twikit_cookies.json"

            if os.path.exists(cookies_file):
                client.load_cookies(cookies_file)
                logger.info("Twikit: loaded saved cookies")
            elif x_user and x_email and x_pass:
                await client.login(auth_info_1=x_email, auth_info_2=x_user, password=x_pass)
                client.save_cookies(cookies_file)
                logger.info("Twikit: logged in and saved cookies")
            else:
                logger.debug("Twikit: no X credentials in .env, skipping authenticated mode")
                self._available = False
                return

            self._client = client
        except Exception as e:
            logger.warning(f"Twikit init failed: {e}")
            self._available = False

    async def fetch(self) -> Optional[List[Dict[str, Any]]]:
        if not self._available:
            return None
        try:
            await self._init_client()
            if not self._client:
                return None

            user = await self._client.get_user_by_screen_name(self.username)
            tweets = await user.get_tweets("Tweets", count=20)
            posts = []
            for t in tweets:
                posts.append({
                    'guid': str(t.id),
                    'title': t.text[:100] if t.text else '',
                    'description': t.text or '',
                    'link': f"https://x.com/{self.username}/status/{t.id}",
                    'pubDate': str(t.created_at) if hasattr(t, 'created_at') else ''
                })
            if posts:
                logger.info(f"Twikit: {len(posts)} tweets fetched")
            return posts
        except Exception as e:
            logger.warning(f"Twikit fetch error: {e}")
            return None


class XTracker:
    """
    Multi-engine X account tracker.
    Engine 1: Nitter RSS mirrors (no auth, rotates automatically)
    Engine 2: Twikit (X guest/cookie API — optional, more reliable)
    """

    def __init__(self, username: str, nitter_instances: List[str]):
        self.username = username.strip("@").strip()
        self._nitter = NitterEngine(self.username, nitter_instances)
        self._twikit = TwikitEngine(self.username)

    async def fetch_latest_posts(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Try Nitter first. If all mirrors are rate-limited (returns None),
        fall back to Twikit. Returns empty list if account not found/private.
        """
        # Try Nitter
        result = await self._nitter.fetch(timeout=timeout)

        if result is None:
            # All Nitter mirrors rate-limited — try Twikit fallback
            logger.info("Nitter rate-limited, trying Twikit fallback...")
            result = await self._twikit.fetch()

        if result is None:
            # Both engines failed — return empty, retry next cycle
            logger.warning("Both Nitter and Twikit unavailable. Retrying next poll cycle.")
            return []

        return result
