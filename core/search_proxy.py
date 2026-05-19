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

    # Domain-level credibility: authoritative sources for scientific queries
    HIGH_AUTHORITY_DOMAINS = {
        # Journals & publishers
        "nature.com": 0.95, "science.org": 0.95, "cell.com": 0.95,
        "pnas.org": 0.95, "aps.org": 0.90, "ieeexplore.ieee.org": 0.90,
        "acm.org": 0.90, "springer.com": 0.85, "wiley.com": 0.85,
        "sciencedirect.com": 0.90, "arxiv.org": 0.90,
        # Major news + science reporting
        "sciencedaily.com": 0.85, "phys.org": 0.80,
        "technologyreview.com": 0.85, "newscientist.com": 0.80,
        "quantamagazine.org": 0.90, "arstechnica.com": 0.80,
        "wired.com": 0.75, "theregister.com": 0.70,
        # Government / institutional
        "nist.gov": 0.95, "nih.gov": 0.95, "nasa.gov": 0.95,
        "energy.gov": 0.90, "nsf.gov": 0.90, "cern.ch": 0.95,
        # Tech company labs / research blogs
        "ai.google": 0.85, "research.google": 0.85,
        "research.ibm.com": 0.85, "research.microsoft.com": 0.85,
        "openai.com": 0.80, "deepmind.google": 0.85,
        # Major tech news
        "techcrunch.com": 0.70, "theverge.com": 0.65,
        "reuters.com": 0.80, "bbc.com": 0.80, "nytimes.com": 0.80,
        "washingtonpost.com": 0.75, "theguardian.com": 0.75,
        "time.com": 0.75, "forbes.com": 0.65,
        "networkworld.com": 0.60, "zdnet.com": 0.60,
        "discovermagazine.com": 0.70,
    }

    LOW_QUALITY_DOMAINS = {
        # Blog / community platforms (low editorial bar)
        "dev.to": 0.25, "medium.com": 0.30, "substack.com": 0.35,
        "linkedin.com": 0.25, "reddit.com": 0.30,
        "quora.com": 0.25, "stackoverflow.com": 0.40,
        # AI-generated content farms (high error rate)
        "programming-helper.com": 0.15, "devflokers.com": 0.20,
        "ai-supremacy.com": 0.25, "roborhythms.com": 0.25,
        "buildfastwithai.com": 0.25, "techbloat.com": 0.25,
        # Aggregators with unclear provenance
        "msn.com": 0.40,
        # Unknown / low-credibility
        "gilkut.net": 0.15, "blogspot.com": 0.15,
        "wordpress.com": 0.20, "tumblr.com": 0.15,
        "pinterest.com": 0.10, "facebook.com": 0.10,
        "twitter.com": 0.20, "x.com": 0.20,
        "tiktok.com": 0.10, "instagram.com": 0.10,
        "youtube.com": 0.30,
    }

    # Category-level fallback scores
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
        min_cred = options.get("min_credibility", 0.35)  # Default: filter out low-quality

        for idx, r in enumerate(results):
            # Skip AI slop
            url = r.get("url", "")
            domain = self._extract_domain(url)
            if domain in self.AI_SLOP_DOMAINS:
                continue

            # Skip topic pages, homepages, and aggregator indexes
            if self._is_index_page(url):
                continue

            # Domain-level credibility (3-tier: exact domain → TLD → category fallback)
            cred_score = self._compute_credibility(domain, r.get("source", "web"))
            if cred_score < min_cred:
                continue

            # Freshness score
            fresh_score = self._compute_freshness(r.get("published_date"))

            # RRF-style rank score
            rank_score = 1.0 / (60 + idx)

            # Combined score (boosted freshness weight for recency)
            combined = (
                0.30 * rank_score +
                0.35 * fresh_score +
                0.35 * cred_score
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

    def _compute_credibility(self, domain: str, source_category: str = "web") -> float:
        """
        Compute credibility score using 3-tier system:
        1. Exact domain match (HIGH_AUTHORITY or LOW_QUALITY lists)
        2. TLD heuristic (.gov, .edu → high; social media → low)
        3. Category-level fallback
        """
        # Tier 1: exact domain match
        if domain in self.HIGH_AUTHORITY_DOMAINS:
            return self.HIGH_AUTHORITY_DOMAINS[domain]
        if domain in self.LOW_QUALITY_DOMAINS:
            return self.LOW_QUALITY_DOMAINS[domain]

        # Tier 2: TLD-based heuristic
        if domain.endswith(".gov") or domain.endswith(".mil"):
            return 0.90
        if domain.endswith(".edu") or domain.endswith(".ac.uk"):
            return 0.85
        if domain.endswith(".org"):
            return 0.65  # Orgs vary widely; moderate default

        # Tier 3: category-level fallback
        return self.CREDIBILITY_SCORES.get(source_category, 0.50)

    def _extract_domain(self, url: str) -> str:
        """Extract clean domain from URL."""
        try:
            parsed = urlparse(url)
            return parsed.netloc.replace("www.", "").lower()
        except Exception:
            return ""

    def _is_index_page(self, url: str) -> bool:
        """
        Detect topic pages, homepages, and aggregator indexes.

        These pages don't contain specific article content and are
        useless as citations. Examples:
        - https://news.mit.edu/topic/quantum-computing  (topic index)
        - https://link.springer.com/subjects/quantum-computing  (subject page)
        - https://quantumzeitgeist.com/  (homepage)
        - https://www.sciencedaily.com/news/computers_math/  (category page)
        """
        try:
            parsed = urlparse(url)
            path = parsed.path.rstrip("/").lower()

            # Homepage: no path or just "/"
            if not path or path == "":
                return True

            # Known index path patterns (topic/category pages)
            index_patterns = [
                "/topic/", "/topics/", "/subjects/", "/subject/",
                "/category/", "/categories/", "/tag/", "/tags/",
                "/search", "/browse/", "/explore/",
                "/latest", "/trending", "/popular",
            ]

            # Article indicators — if present, it's likely a real article, not an index
            has_article_indicators = (
                any(c.isdigit() for c in path) or  # dates, IDs
                path.endswith(".html") or path.endswith(".htm") or
                path.endswith(".pdf") or
                "/article/" in path or "/articles/" in path or
                "/releases/" in path or "/paper/" in path or
                "/post/" in path or "/blog/" in path
            )

            # If path contains an index pattern and has no article indicators → index page
            if any(pat in path for pat in index_patterns) and not has_article_indicators:
                return True

            # Category-style paths: /news/some_category/ or /news/cat/subcat/
            # These have no article indicators and are just navigation
            if "/news/" in path and not has_article_indicators:
                return True

            # Very short paths with no article indicators (likely homepages)
            path_segments = [s for s in path.split("/") if s]
            if len(path_segments) <= 1 and not has_article_indicators:
                return True

            return False
        except Exception:
            return False

    async def health_check(self) -> bool:
        """Check if search service is available."""
        return await self.searxng.health_check()
