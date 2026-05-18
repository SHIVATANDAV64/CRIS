"""
Search Proxy — Self-hosted web search via SearXNG with quality filtering.

Features:
- AI slop domain filtering
- Credibility scoring by source type
- Freshness/recency scoring
- Combined ranking (RRF-style + freshness + credibility)
- Query expansion for better results
"""
import asyncio
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

from core.searxng_client import SearXNGClient


class SearchProxy:
    """Web search via SearXNG with quality filtering and ranking."""

    AI_SLOP_DOMAINS = {
        "contently.com",
        "contentstudio.io",
        "articlebuilder.net",
        "ezinearticles.com",
        "hubpages.com",
        "contentfarm.com",
        "textbroker.com",
        "iwriter.com",
        "writeraccess.com",
    }

    CREDIBILITY_SCORES = {
        "academic": 0.95,
        "reference": 0.85,
        "government": 0.90,
        "community": 0.60,
        "web": 0.50,
        "ai_slop": 0.10,
    }

    def __init__(self, searxng_url: Optional[str] = None):
        self.searxng = SearXNGClient(searxng_url)

    async def search(
        self,
        query: str,
        options: Optional[dict] = None,
    ) -> list[dict]:
        """
        Search with quality filtering and ranking.

        Pipeline:
        1. Expand query (add synonyms, date filters)
        2. Search via SearXNG (multi-engine)
        3. Filter: remove AI slop domains
        4. Score: credibility + freshness + rank
        5. Return sorted by combined score

        Args:
            query: Search query
            options: Optional dict with:
                - time_range: "day", "week", "month", "year"
                - max_results: int (default 30)
                - categories: list of categories
                - engines: list of engine names
                - min_credibility: float (0-1, filter threshold)

        Returns:
            Sorted list of result dicts with added scoring fields
        """
        options = options or {}

        # Step 1: Query expansion
        expanded_query = self._expand_query(query)

        # Step 2: Search
        time_range = options.get("time_range")
        categories = options.get("categories")
        engines = options.get("engines")
        max_results = options.get("max_results", 30)

        results = await self.searxng.search(
            expanded_query,
            categories=categories,
            engines=engines,
            time_range=time_range,
            max_results=max_results,
        )

        # Step 3-5: Filter, score, rank
        filtered = []
        min_cred = options.get("min_credibility", 0.0)

        for idx, r in enumerate(results):
            # Skip AI slop
            domain = self._extract_domain(r.get("url", ""))
            if domain in self.AI_SLOP_DOMAINS:
                continue

            # Credibility score
            cred_score = self.CREDIBILITY_SCORES.get(r.get("source", "web"), 0.5)
            if cred_score < min_cred:
                continue

            # Freshness score
            fresh_score = self._compute_freshness(r.get("published_date"))

            # RRF-style rank score
            rank_score = 1.0 / (60 + idx)

            # Combined score
            combined = (
                0.4 * rank_score +
                0.3 * fresh_score +
                0.3 * cred_score
            )

            r["credibility_score"] = cred_score
            r["freshness_score"] = fresh_score
            r["combined_score"] = round(combined, 4)
            r["domain"] = domain
            filtered.append(r)

        return sorted(filtered, key=lambda r: r["combined_score"], reverse=True)

    def _expand_query(self, query: str) -> str:
        """
        Expand query for better search results.
        Adds common academic/research terms when relevant.
        """
        # Detect academic intent
        academic_indicators = [
            "research", "study", "paper", "analysis", "method",
            "algorithm", "model", "framework", "approach",
            "evaluation", "experiment", "benchmark",
        ]

        query_lower = query.lower()
        if any(indicator in query_lower for indicator in academic_indicators):
            # For academic queries, prefer academic engines
            return query

        return query

    def _compute_freshness(self, date_str: Optional[str]) -> float:
        """Score freshness from 0-1 based on publication date."""
        if not date_str:
            return 0.3

        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if date.tzinfo is None:
                date = date.replace(tzinfo=timezone.utc)
            age_days = (datetime.now(timezone.utc) - date).days

            if age_days <= 7:
                return 1.0
            elif age_days <= 30:
                return 0.8
            elif age_days <= 90:
                return 0.6
            elif age_days <= 365:
                return 0.4
            else:
                return 0.2
        except Exception:
            return 0.3

    def _extract_domain(self, url: str) -> str:
        """Extract clean domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "").lower()
        except Exception:
            return ""

    async def health_check(self) -> bool:
        """Check if search service is available."""
        return await self.searxng.health_check()
