import asyncio
import feedparser
import httpx
import logging
import re
import os
import time
from typing import List, Dict, Any, Optional

logger = logging.getLogger("XTracker")

# Extended list of known working Nitter public instances
DEFAULT_NITTER_INSTANCES = [
    "https://nitter.net",
    "https://nitter.poast.org",
    "https://privacydev.net",
    "https://nitter.privacydev.net",
    "https://nitter.hu",
    "https://nitter.cz",
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


def clean_tweet_url(raw_url: str, target_username: str = "") -> str:
    """
    Extracts status ID from ANY nitter/x/twitter/fxtwitter/vxtwitter URL
    and returns clean, standardized https://x.com/<username>/status/<id>
    """
    if not raw_url:
        return ""
    
    # Clean anchor tags like #m
    raw_url = raw_url.split('#')[0].strip()

    # Extract status ID (numeric string of 15+ digits)
    status_match = re.search(r'/status/(\d+)', raw_url)
    if status_match:
        status_id = status_match.group(1)
        # Extract username if available from URL, else use target_username
        user_match = re.search(r'https?://[^/]+/([^/]+)/status/\d+', raw_url)
        username = target_username
        if user_match and user_match.group(1).lower() not in ['status', 'i']:
            username = user_match.group(1)
        username = username.replace('@', '').strip()
        if not username:
            username = "x"
        return f"https://x.com/{username}/status/{status_id}"
    
    # If no status ID found, clean up domain
    clean_url = re.sub(r'https?://[^/]+', 'https://x.com', raw_url)
    return clean_url


class NitterEngine:
    """Fetches X posts via public Nitter RSS mirrors with cache-busting."""

    def __init__(self, username: str, instances: List[str]):
        self.username = username.strip("@").strip()
        sanitized = [_sanitize_url(u) for u in instances if u.strip()]
        seen, merged = set(), []
        for url in sanitized + DEFAULT_NITTER_INSTANCES:
            if url not in seen:
                seen.add(url)
                merged.append(url)
        self.instances = merged
        self.idx = 0

    def _current_url(self) -> str:
        # Add timestamp parameter to prevent proxy/CDN caching
        ts = int(time.time())
        return f"{self.instances[self.idx]}/{self.username}/rss?ts={ts}"

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
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Cache-Control": "no-cache, no-store, must-revalidate",
            "Pragma": "no-cache",
            "Expires": "0"
        }

        for _ in range(len(self.instances)):
            url = self._current_url()
            try:
                async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
                    resp = await client.get(url, headers=headers)

                if resp.status_code == 200:
                    if not resp.text or len(resp.text.strip()) == 0:
                        logger.warning(f"Nitter returned empty response from {url}, rotating...")
                        self._rotate()
                        await asyncio.sleep(0.3)
                        continue

                    feed = feedparser.parse(resp.text)
                    if not feed.entries:
                        logger.warning(f"Feed returned 0 entries from {url}, rotating...")
                        self._rotate()
                        await asyncio.sleep(0.3)
                        continue

                    posts = []
                    for entry in feed.entries:
                        raw_guid = getattr(entry, 'guid', None) or getattr(entry, 'link', None) or ''
                        raw_link = getattr(entry, 'link', '') or str(raw_guid)
                        
                        clean_link = clean_tweet_url(raw_link, self.username)
                        guid_clean = clean_tweet_url(str(raw_guid), self.username) or clean_link

                        posts.append({
                            'guid': guid_clean,
                            'title': getattr(entry, 'title', ''),
                            'description': getattr(entry, 'description', '') or getattr(entry, 'summary', ''),
                            'link': clean_link,
                            'pubDate': getattr(entry, 'published', '')
                        })
                    
                    if posts:
                        logger.debug(f"Nitter: {len(posts)} posts fetched from {self.instances[self.idx]}")
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
            await asyncio.sleep(0.3)

        logger.warning("All Nitter mirrors rate-limited or unavailable.")
        return None  # None = try fallback engines


class VxTwitterEngine:
    """
    Fetches user status and latest tweets via VxTwitter & FixTweet public APIs.
    Acts as a resilient secondary fallback when Nitter is down.
    """

    def __init__(self, username: str):
        self.username = username.strip("@").strip()

    async def fetch(self, timeout: float = 6.0) -> Optional[List[Dict[str, Any]]]:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        urls = [
            f"https://api.vxtwitter.com/{self.username}",
            f"https://api.fxtwitter.com/{self.username}"
        ]

        async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
            for u in urls:
                try:
                    resp = await client.get(u, headers=headers)
                    if resp.status_code == 200:
                        data = resp.json()
                        # Some VxTwitter endpoints return user profile metadata
                        if isinstance(data, dict):
                            user_id = data.get("id")
                            tweet_count = data.get("tweet_count")
                            # If recent tweet is present in payload
                            tweet = data.get("tweet") or data.get("latest_tweet")
                            if tweet and isinstance(tweet, dict):
                                tweet_id = str(tweet.get("id") or tweet.get("id_str") or "")
                                text = tweet.get("text") or tweet.get("description") or ""
                                if tweet_id:
                                    clean_link = f"https://x.com/{self.username}/status/{tweet_id}"
                                    logger.info(f"VxTwitter API: latest tweet fetched (ID: {tweet_id})")
                                    return [{
                                        'guid': clean_link,
                                        'title': text[:100],
                                        'description': text,
                                        'link': clean_link,
                                        'pubDate': tweet.get("created_at", "")
                                    }]
                except Exception as e:
                    logger.debug(f"VxTwitter error for {u}: {e}")

        return None


class TwikitEngine:
    """
    Fetches X posts via Twikit (X GraphQL API).
    Supports:
    - X_AUTH_TOKEN in .env (instant cookie auth)
    - X_USERNAME, X_EMAIL, X_PASSWORD in .env
    - Saved twikit_cookies.json file
    """

    def __init__(self, username: str):
        self.username = username.strip("@").strip()
        self._client = None
        self._available = False
        try:
            from twikit import Client  # noqa
            self._available = True
        except ImportError:
            logger.debug("Twikit package not installed — skipping Twikit engine")

    def is_authenticated(self) -> bool:
        """Check if X credentials or cookie files are present."""
        if not self._available:
            return False
        has_auth_token = bool(os.getenv("X_AUTH_TOKEN", "").strip())
        has_creds = bool(os.getenv("X_USERNAME", "").strip() and os.getenv("X_PASSWORD", "").strip())
        has_cookies = os.path.exists("twikit_cookies.json")
        return has_auth_token or has_creds or has_cookies

    async def _init_client(self):
        if not self._available or self._client is not None:
            return
        try:
            from twikit import Client
            client = Client("en-US")
            
            auth_token = os.getenv("X_AUTH_TOKEN", "").strip()
            x_user = os.getenv("X_USERNAME", "").strip()
            x_email = os.getenv("X_EMAIL", "").strip()
            x_pass = os.getenv("X_PASSWORD", "").strip()
            cookies_file = "twikit_cookies.json"

            if auth_token:
                # Direct auth token injection
                client.set_cookies({"auth_token": auth_token})
                logger.info("Twikit: authenticated via X_AUTH_TOKEN")
            elif os.path.exists(cookies_file):
                client.load_cookies(cookies_file)
                logger.info("Twikit: loaded saved cookies")
            elif x_user and x_pass:
                await client.login(auth_info_1=x_email or x_user, auth_info_2=x_user, password=x_pass)
                client.save_cookies(cookies_file)
                logger.info("Twikit: logged in and saved cookies")
            else:
                logger.debug("Twikit: no X credentials/cookies in .env, running guest mode")
                return

            self._client = client
        except Exception as e:
            logger.warning(f"Twikit init failed: {e}")
            self._client = None

    async def fetch(self) -> Optional[List[Dict[str, Any]]]:
        if not self._available:
            return None
        try:
            await self._init_client()
            if not self._client:
                return None

            user = await self._client.get_user_by_screen_name(self.username)
            tweets = await user.get_tweets("Tweets", count=15)
            posts = []
            for t in tweets:
                clean_link = f"https://x.com/{self.username}/status/{t.id}"
                posts.append({
                    'guid': clean_link,
                    'title': t.text[:100] if t.text else '',
                    'description': t.text or '',
                    'link': clean_link,
                    'pubDate': str(t.created_at) if hasattr(t, 'created_at') else ''
                })
            if posts:
                logger.info(f"Twikit: {len(posts)} tweets fetched for @{self.username}")
            return posts
        except Exception as e:
            logger.warning(f"Twikit fetch error: {e}")
            return None


class XTracker:
    """
    Multi-engine X account tracker.
    Engine 1: Twikit (if authenticated via credentials/cookies, runs first for 0-latency detection)
    Engine 2: Nitter RSS mirrors (rotates public mirrors with cache-busting)
    Engine 3: VxTwitter API fallback
    """

    def __init__(self, username: str, nitter_instances: List[str]):
        self.username = username.strip("@").strip()
        self._nitter = NitterEngine(self.username, nitter_instances)
        self._twikit = TwikitEngine(self.username)
        self._vxtwitter = VxTwitterEngine(self.username)

    async def fetch_latest_posts(self, timeout: float = 5.0) -> List[Dict[str, Any]]:
        """
        Multi-layered fetch strategy:
        1. If Twikit is authenticated, try Twikit first.
        2. Try Nitter RSS with cache-busting.
        3. If Nitter rate-limits, try VxTwitter API.
        """
        # If Twikit is configured with credentials/auth_token, priority goes to Twikit
        if self._twikit.is_authenticated():
            result = await self._twikit.fetch()
            if result:
                return result

        # Try Nitter RSS with cache-busting
        result = await self._nitter.fetch(timeout=timeout)

        # Fallback to VxTwitter API if Nitter fails/rate-limits
        if result is None:
            logger.info("Nitter unavailable, trying VxTwitter fallback API...")
            result = await self._vxtwitter.fetch(timeout=timeout)

        # Final fallback to Twikit if not attempted yet
        if result is None and not self._twikit.is_authenticated():
            logger.info("Trying Twikit fallback...")
            result = await self._twikit.fetch()

        if result is None:
            logger.warning("All tracking engines unavailable. Retrying next poll cycle.")
            return []

        return result
