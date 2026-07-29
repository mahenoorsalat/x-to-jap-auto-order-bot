import re
from typing import Optional, List
from bs4 import BeautifulSoup
import httpx

# Regex to capture valid HTTP/HTTPS URLs
URL_REGEX = r'https?://[^\s<>"]+|www\.[^\s<>"]+'

class LinkParser:
    @staticmethod
    def extract_links_from_text(html_or_text: str) -> List[str]:
        """Clean HTML tags if any and extract all raw URLs."""
        if not html_or_text:
            return []

        # Parse HTML text if content contains markup (common in RSS feeds)
        soup = BeautifulSoup(html_or_text, "html.parser")
        
        # Check href attributes first
        links_from_hrefs = [a['href'] for a in soup.find_all('a', href=True)]
        
        # Also run Regex on text content
        clean_text = soup.get_text(separator=" ")
        links_from_regex = re.findall(URL_REGEX, clean_text)
        
        # Combine unique links maintaining order
        all_links = []
        for url in links_from_hrefs + links_from_regex:
            url = url.rstrip('.,;()[]"\'')
            if url and url not in all_links:
                all_links.append(url)
                
        return all_links

    @staticmethod
    async def resolve_redirect(url: str, timeout: float = 3.0) -> str:
        """Resolve short URLs (e.g., t.co, bit.ly) to destination URL."""
        if not ("t.co" in url or "bit.ly" in url or "tinyurl.com" in url or "goo.gl" in url):
            return url
            
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                res = await client.head(url)
                return str(res.url)
        except Exception:
            try:
                async with httpx.AsyncClient(follow_redirects=True, timeout=timeout) as client:
                    res = await client.get(url)
                    return str(res.url)
            except Exception:
                return url

    @classmethod
    async def get_first_target_url(cls, html_or_text: str) -> Optional[str]:
        """Extract and resolve the first destination URL found in post text."""
        raw_links = cls.extract_links_from_text(html_or_text)
        
        # Filter out Twitter/Nitter self-referencing links if needed, or take first valid URL
        for link in raw_links:
            # Ignore standard twitter post anchor links (e.g. nitter.net/status/...) if they point to the post itself
            if "/status/" in link and ("nitter" in link or "x.com" in link or "twitter.com" in link):
                continue
            resolved = await cls.resolve_redirect(link)
            return resolved
            
        # If all links were twitter status links, return first resolved link as fallback
        if raw_links:
            return await cls.resolve_redirect(raw_links[0])
            
        return None
