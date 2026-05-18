"""
Web Search & Scraper — Server-side web search and page scraping tools.

Uses SearXNG (Modal-hosted) for multi-engine web search:
- DuckDuckGo (general web)
- Wikipedia (knowledge)
- arXiv (academic papers)
- Hacker News (tech community)

Plus quality filtering, credibility scoring, and freshness ranking.
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
    """Web search via SearXNG (Modal-hosted) with quality filtering."""

    def __init__(self, scraper: Optional[WebScraper] = None, searxng_url: Optional[str] = None):
        self.scraper = scraper or WebScraper()
        self._proxy = None
        self._searxng_url = searxng_url

    def _get_proxy(self):
        """Lazy-init the search proxy."""
        if self._proxy is None:
            from core.search_proxy import SearchProxy
            self._proxy = SearchProxy(self._searxng_url)
        return self._proxy

    async def search(self, query: str, num_results: int = 5, options: Optional[dict] = None) -> list[dict]:
        """
        Search the web via SearXNG with quality filtering.

        Args:
            query: Search query
            num_results: Number of results to return
            options: Optional dict with:
                - time_range: "day", "week", "month", "year"
                - categories: list of categories (general, academic, community, news)
                - engines: list of engine names
                - min_credibility: float (0-1)

        Returns:
            List of search results with title, url, snippet, engine, credibility_score, freshness_score, combined_score
        """
        try:
            proxy = self._get_proxy()
            search_options = options or {}
            search_options["max_results"] = num_results

            results = await proxy.search(query, options=search_options)

            # Format for backward compatibility
            formatted = []
            for r in results[:num_results]:
                formatted.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("snippet", ""),
                    "engine": r.get("engine", ""),
                    "category": r.get("category", ""),
                    "published_date": r.get("published_date"),
                    "credibility_score": r.get("credibility_score", 0.5),
                    "freshness_score": r.get("freshness_score", 0.3),
                    "combined_score": r.get("combined_score", 0.0),
                    "source": r.get("source", "web"),
                })

            if not formatted:
                console.print(f"[yellow]No web results for: {query}[/yellow]")

            return formatted
        except Exception as e:
            console.print(f"[red]Web search error: {e}[/red]")
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

    async def health_check(self) -> bool:
        """Check if search service is available."""
        try:
            proxy = self._get_proxy()
            return await proxy.health_check()
        except Exception:
            return False


# Singleton instances
_scraper = None
_search = None


def get_scraper() -> WebScraper:
    """Get or create the web scraper singleton."""
    global _scraper
    if _scraper is None:
        _scraper = WebScraper()
    return _scraper


def get_search(searxng_url: Optional[str] = None) -> WebSearch:
    """Get or create the web search singleton."""
    global _search
    if _search is None:
        _search = WebSearch(searxng_url=searxng_url)
    return _search
