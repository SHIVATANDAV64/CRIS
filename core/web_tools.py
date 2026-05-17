"""
Web Search & Scraper — Server-side web search and page scraping tools.

Inspired by OpenHuman's approach:
- Web search uses server-side proxy (not direct API calls from client)
- Web scraper uses raw HTTP GET with truncation (1MB cap, 20s timeout)
"""
import re
import time
import httpx
from typing import Optional
from urllib.parse import quote_plus, urlparse

from rich.console import Console

console = Console()


class WebScraper:
    """Simple web scraper with rate limiting and content truncation."""

    MAX_CONTENT_LENGTH = 1_000_000  # 1MB cap
    TIMEOUT = 20  # 20 seconds
    USER_AGENT = "CRIS-Research-Bot/1.0 (Research Assistant)"

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=self.TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": self.USER_AGENT},
        )

    async def scrape_url(self, url: str) -> dict:
        """
        Scrape a URL and return cleaned content.

        Args:
            url: The URL to scrape

        Returns:
            Dict with title, content, metadata
        """
        try:
            response = await self.client.get(url)
            response.raise_for_status()

            # Get content type
            content_type = response.headers.get("content-type", "")

            # Handle different content types
            if "text/html" in content_type:
                return self._parse_html(response.text, url)
            elif "text/plain" in content_type:
                return self._parse_text(response.text, url)
            elif "application/json" in content_type:
                return self._parse_json(response.text, url)
            else:
                return {
                    "url": url,
                    "title": urlparse(url).netloc,
                    "content": response.text[:self.MAX_CONTENT_LENGTH],
                    "content_type": content_type,
                    "status": "success",
                }

        except httpx.TimeoutException:
            return {"url": url, "error": "Timeout", "status": "error"}
        except httpx.HTTPStatusError as e:
            return {"url": url, "error": str(e), "status": "error"}
        except Exception as e:
            return {"url": url, "error": str(e), "status": "error"}

    def _parse_html(self, html: str, url: str) -> dict:
        """Parse HTML and extract text content."""
        # Simple HTML parsing (no external dependencies)
        # Remove script and style elements
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)

        # Extract title
        title_match = re.search(r'<title[^>]*>(.*?)</title>', html, re.IGNORECASE)
        title = title_match.group(1).strip() if title_match else urlparse(url).netloc

        # Extract meta description
        desc_match = re.search(r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']', html, re.IGNORECASE)
        description = desc_match.group(1) if desc_match else ""

        # Extract text content (simple approach)
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()

        # Truncate if too long
        if len(text) > self.MAX_CONTENT_LENGTH:
            text = text[:self.MAX_CONTENT_LENGTH] + "... [truncated]"

        return {
            "url": url,
            "title": title,
            "content": text,
            "description": description,
            "content_type": "text/html",
            "status": "success",
        }

    def _parse_text(self, text: str, url: str) -> dict:
        """Parse plain text content."""
        if len(text) > self.MAX_CONTENT_LENGTH:
            text = text[:self.MAX_CONTENT_LENGTH] + "... [truncated]"

        return {
            "url": url,
            "title": urlparse(url).netloc,
            "content": text,
            "content_type": "text/plain",
            "status": "success",
        }

    def _parse_json(self, text: str, url: str) -> dict:
        """Parse JSON content."""
        if len(text) > self.MAX_CONTENT_LENGTH:
            text = text[:self.MAX_CONTENT_LENGTH] + "... [truncated]"

        return {
            "url": url,
            "title": urlparse(url).netloc,
            "content": text,
            "content_type": "application/json",
            "status": "success",
        }

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()


class WebSearch:
    """Web search using server-side proxy."""

    def __init__(self, scraper: Optional[WebScraper] = None):
        self.scraper = scraper or WebScraper()

    async def search(self, query: str, num_results: int = 5) -> list[dict]:
        """
        Search the web for a query.

        Note: This uses a simple approach. In production, you would use
        a proper search API (Google, Bing, DuckDuckGo, etc.)

        Args:
            query: Search query
            num_results: Number of results to return

        Returns:
            List of search results with title, url, snippet
        """
        # For now, return empty list (would need API key for real search)
        # In production, integrate with:
        # - Google Custom Search API
        # - Bing Web Search API
        # - DuckDuckGo Instant Answer API
        # - SearxNG (self-hosted)

        console.print(f"[yellow]Web search not configured: {query}[/yellow]")
        return []

    async def search_and_scrape(self, query: str, num_results: int = 3) -> list[dict]:
        """
        Search the web and scrape top results.

        Args:
            query: Search query
            num_results: Number of results to scrape

        Returns:
            List of scraped page contents
        """
        results = await self.search(query, num_results)
        scraped = []

        for result in results:
            content = await self.scraper.scrape_url(result["url"])
            if content["status"] == "success":
                scraped.append(content)

        return scraped


# Singleton instances
_scraper = None
_search = None


def get_scraper() -> WebScraper:
    """Get or create the web scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = WebScraper()
    return _scraper


def get_search() -> WebSearch:
    """Get or create the web search singleton."""
    global _search
    if _search is None:
        _search = WebSearch()
    return _search
