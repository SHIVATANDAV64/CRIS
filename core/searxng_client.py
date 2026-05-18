"""
SearXNG Client — Async client for Modal-hosted multi-engine web search.

Connects to the SearXNG service deployed on Modal.com, which aggregates
results from DuckDuckGo, Wikipedia, arXiv, and Hacker News.

Configuration:
    SEARXNG_MODAL_URL=https://<workspace>--cris-searxng-search.modal.run
"""
import httpx
from typing import Optional
from urllib.parse import urlparse

from config.settings import get_config_section


class SearXNGClient:
    """Modal-hosted SearXNG client for multi-engine web search."""

    def __init__(self, base_url: Optional[str] = None):
        if base_url:
            self.base_url = base_url.rstrip("/")
        else:
            search_config = get_config_section("search")
            self.base_url = search_config.get("searxng_url", "").rstrip("/")

    async def search(
        self,
        query: str,
        categories: Optional[list[str]] = None,
        engines: Optional[list[str]] = None,
        time_range: Optional[str] = None,
        language: str = "en",
        max_results: int = 20,
    ) -> list[dict]:
        """
        Search across multiple engines via SearXNG.

        Args:
            query: Search query string
            categories: Filter by category: general, academic, community, news
            engines: Specific engines: duckduckgo, wikipedia, arxiv, hackernews
            time_range: day, week, month, year
            language: Language code (default: en)
            max_results: Maximum results to return

        Returns:
            List of result dicts with title, url, content, engine, category, publishedDate
        """
        if not self.base_url:
            return []

        params: dict = {
            "q": query,
            "language": language,
            "format": "json",
            "max_results": max_results,
        }
        if categories:
            params["categories"] = ",".join(categories)
        if engines:
            params["engines"] = ",".join(engines)
        if time_range:
            params["time_range"] = time_range

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(f"{self.base_url}/search", params=params)
                resp.raise_for_status()
                data = resp.json()

            results = []
            for r in data.get("results", [])[:max_results]:
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "snippet": r.get("content", ""),
                    "engine": r.get("engine", ""),
                    "category": r.get("category", ""),
                    "published_date": r.get("publishedDate"),
                    "source": self._classify_source(r.get("url", "")),
                })

            return results
        except httpx.TimeoutException:
            return []
        except httpx.HTTPStatusError:
            return []
        except Exception:
            return []

    def _classify_source(self, url: str) -> str:
        """Classify source type for credibility scoring."""
        if not url:
            return "web"
        if "arxiv.org" in url:
            return "academic"
        if "pubmed" in url or "ncbi.nlm.nih.gov" in url:
            return "academic"
        if "wikipedia.org" in url:
            return "reference"
        if "reddit.com" in url:
            return "community"
        if "news.ycombinator.com" in url or "hn.algolia.com" in url:
            return "community"
        if "scholar.google.com" in url:
            return "academic"
        if ".gov" in url:
            return "government"
        if ".edu" in url:
            return "academic"
        return "web"

    async def health_check(self) -> bool:
        """Check if the SearXNG service is reachable."""
        if not self.base_url:
            return False
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except Exception:
            return False
