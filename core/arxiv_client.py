"""
arXiv OAI-PMH Client — Fetches paper metadata from arXiv using the OAI-PMH protocol.
Uses the `sickle` library which handles resumption tokens and pagination automatically.

Supports both legacy date-based storage and new domain-based storage.
"""
import json
import time
import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from config.settings import (
    ARXIV_OAI_URL,
    ARXIV_RATE_LIMIT_SECONDS,
    ARXIV_CATEGORIES,
    RAW_DIR,
)


def _parse_arxiv_record(record) -> Optional[dict]:
    """Parse a single OAI-PMH record into a clean paper dict."""
    try:
        meta = record.metadata
        if not meta:
            return None

        header = record.header
        oai_id = header.identifier if header else ""
        arxiv_id = oai_id.replace("oai:arXiv.org:", "") if oai_id else ""

        if not arxiv_id:
            return None

        title = meta.get("title", [""])[0] if isinstance(meta.get("title"), list) else meta.get("title", "")
        abstract = meta.get("abstract", [""])[0] if isinstance(meta.get("abstract"), list) else meta.get("abstract", "")
        authors = meta.get("authors", []) if isinstance(meta.get("authors"), list) else [meta.get("authors", "")]
        categories = meta.get("categories", [""])[0] if isinstance(meta.get("categories"), list) else meta.get("categories", "")
        created = meta.get("created", [""])[0] if isinstance(meta.get("created"), list) else meta.get("created", "")

        title = re.sub(r'\s+', ' ', title).strip()
        abstract = re.sub(r'\s+', ' ', abstract).strip()

        if not title or not abstract:
            return None

        return {
            "arxiv_id": arxiv_id,
            "title": title,
            "abstract": abstract,
            "authors": authors if isinstance(authors, list) else [authors],
            "categories": categories,
            "created": created,
            "fetched_at": datetime.now().isoformat(),
        }
    except Exception as e:
        print(f"Warning: Failed to parse record: {e}")
        return None


def fetch_papers(
    from_date: str,
    until_date: Optional[str] = None,
    categories: Optional[list] = None,
    max_papers: Optional[int] = None,
    is_cancelled: Optional[callable] = None,
    on_log: Optional[callable] = None,
    on_paper_fetched: Optional[callable] = None,
    on_category_start: Optional[callable] = None,
) -> list[dict]:
    """
    Fetch papers from arXiv via OAI-PMH.

    Args:
        from_date: Start date in YYYY-MM-DD format
        until_date: End date in YYYY-MM-DD format (optional)
        categories: List of arXiv categories to filter (optional, uses config default)
        max_papers: Maximum number of papers to fetch (optional, for testing)
        is_cancelled: Optional callable to check if execution should stop
        on_log: Optional callback function to record logs
        on_paper_fetched: Optional callback for each paper fetched
        on_category_start: Optional callback when starting a new category fetch

    Returns:
        List of paper dicts with: arxiv_id, title, abstract, authors, categories, created
    """
    from sickle import Sickle

    cats = categories or ARXIV_CATEGORIES
    sickle = Sickle(ARXIV_OAI_URL)
    all_papers = []

    def log(msg: str):
        print(msg)
        if on_log:
            on_log(msg)

    for cat_idx, category in enumerate(cats):
        if is_cancelled and is_cancelled():
            log("Fetch cancelled by caller.")
            break

        if on_category_start:
            on_category_start(category, cat_idx)

        log(f"\nFetching papers from {category} (from {from_date})...")

        params = {
            "metadataPrefix": "arXiv",
            "from": from_date,
            "set": f"cs" if category.startswith("cs") else category.split(".")[0],
        }
        if until_date:
            params["until"] = until_date

        category_papers = []
        try:
            records = sickle.ListRecords(**params)

            for record in records:
                if is_cancelled and is_cancelled():
                    log("Fetch cancelled mid-record loop.")
                    break

                paper = _parse_arxiv_record(record)
                if paper is None:
                    continue

                paper_cats = paper.get("categories", "")
                if category not in paper_cats:
                    continue

                category_papers.append(paper)
                if on_paper_fetched:
                    on_paper_fetched(paper)
                if len(category_papers) % 10 == 0:
                    log(f"  ... {len(category_papers)} papers so far in {category}")

                if max_papers and len(category_papers) >= max_papers:
                    break

                # Cancel-aware sleep: check is_cancelled every 100ms
                for _ in range(int(ARXIV_RATE_LIMIT_SECONDS * 10)):
                    if is_cancelled and is_cancelled():
                        break
                    time.sleep(0.1)

        except Exception as e:
            error_msg = str(e)
            if "noRecordsMatch" in error_msg:
                log(f"  No papers found for {category} on {from_date}")
            else:
                log(f"  Error fetching {category}: {e}")

        log(f"  Found {len(category_papers)} papers in {category}")
        all_papers.extend(category_papers)

    return all_papers


def save_papers(papers: list[dict], date_str: str, on_log: Optional[callable] = None) -> Path:
    """
    Save fetched papers as individual JSON files organized by date (legacy mode).

    Args:
        papers: List of paper dicts from fetch_papers()
        date_str: Date string (YYYY-MM-DD) for directory naming
        on_log: Optional callback function to record logs

    Returns:
        Path to the date directory where papers were saved
    """
    date_dir = RAW_DIR / date_str
    date_dir.mkdir(parents=True, exist_ok=True)

    saved = 0
    skipped = 0

    def log(msg: str):
        print(msg)
        if on_log:
            on_log(msg)

    for paper in papers:
        arxiv_id = paper["arxiv_id"]
        safe_id = arxiv_id.replace("/", "_")
        filepath = date_dir / f"{safe_id}.json"

        if filepath.exists():
            skipped += 1
            continue

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(paper, f, indent=2, ensure_ascii=False)
        saved += 1

    log(f"\nSaved {saved} papers to {date_dir}")
    if skipped:
        log(f"Skipped {skipped} already existing")

    return date_dir


def save_papers_by_domain(papers: list[dict], on_log: Optional[callable] = None) -> dict[str, int]:
    """
    Save papers organized by domain folders.

    Structure: data/raw/<domain>/<date>/<paper_id>.json

    Args:
        papers: List of paper dicts from fetch_papers()
        on_log: Optional callback function to record logs

    Returns:
        Dict mapping domain -> count of papers saved
    """
    from core.domain_manager import save_paper_by_domain, _extract_domains

    counts = {}
    saved = 0
    skipped = 0

    def log(msg: str):
        print(msg)
        if on_log:
            on_log(msg)

    for paper in papers:
        domains = _extract_domains(paper)
        date_str = paper.get("created", "")[:10] or datetime.now().strftime("%Y-%m-%d")

        for domain in domains:
            filepath = save_paper_by_domain(paper, domain, date_str)
            if filepath.exists():
                is_new = filepath.stat().st_mtime > time.time() - 5
                if is_new:
                    counts[domain] = counts.get(domain, 0) + 1
                    saved += 1
                else:
                    skipped += 1

    log(f"\nSaved {saved} papers by domain")
    if skipped:
        log(f"Skipped {skipped} already existing")

    return counts


def load_papers(date_str: str) -> list[dict]:
    """Load all paper JSONs for a given date (legacy mode)."""
    date_dir = RAW_DIR / date_str
    if not date_dir.exists():
        return []

    papers = []
    for f in sorted(date_dir.glob("*.json")):
        with open(f, "r", encoding="utf-8") as fh:
            papers.append(json.load(fh))
    return papers


def load_papers_by_domain(domain: str) -> list[dict]:
    """Load all papers for a domain from domain-based storage."""
    from core.domain_manager import get_papers_for_domain
    return get_papers_for_domain(domain)
