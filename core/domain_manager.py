"""
Domain Manager — Organizes papers by domain folders and provides browsing APIs.

Storage structure (legacy date-based):
    data/raw/
        2026-05-14/
            2605.12345.json
            2605.12346.json

Storage structure (new domain-based):
    data/raw/
        cs_AI/
            2026-05-14/
                2605.12345.json
"""
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional

from config.settings import RAW_DIR


DOMAIN_DISPLAY_NAMES = {
    "cs.AI": "Artificial Intelligence",
    "cs.CL": "Computation & Language",
    "cs.LG": "Machine Learning",
    "q-bio.BM": "Biomolecules",
    "cs.CV": "Computer Vision",
    "cs.RO": "Robotics",
    "cs.SE": "Software Engineering",
    "cs.CR": "Cryptography & Security",
    "cs.DB": "Databases",
    "cs.IR": "Information Retrieval",
    "cs.NE": "Neural Networks",
    "cs.HC": "Human-Computer Interaction",
    "stat.ML": "Machine Learning (Stats)",
    "q-bio.QM": "Quantitative Methods",
    "physics.data-an": "Data Analysis (Physics)",
    "math.ST": "Statistics (Math)",
}


def _get_domain_folder(domain: str) -> Path:
    safe_domain = domain.replace("/", "_")
    return RAW_DIR / safe_domain


def save_paper_by_domain(paper: dict, domain: str, date_str: Optional[str] = None) -> Path:
    if not date_str:
        date_str = paper.get("created", "")[:10] or datetime.now().strftime("%Y-%m-%d")

    domain_folder = _get_domain_folder(domain)
    date_folder = domain_folder / date_str
    date_folder.mkdir(parents=True, exist_ok=True)

    arxiv_id = paper["arxiv_id"]
    safe_id = arxiv_id.replace("/", "_")
    filepath = date_folder / f"{safe_id}.json"

    if filepath.exists():
        return filepath

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(paper, f, indent=2, ensure_ascii=False)

    return filepath


def save_papers_by_domain(papers: list[dict], domains: Optional[list[str]] = None) -> dict[str, int]:
    counts = {}
    for paper in papers:
        paper_domains = domains or _extract_domains(paper)
        date_str = paper.get("created", "")[:10] or datetime.now().strftime("%Y-%m-%d")
        for domain in paper_domains:
            filepath = save_paper_by_domain(paper, domain, date_str)
            if filepath.exists():
                counts[domain] = counts.get(domain, 0) + 1
    return counts


def _extract_domains(paper: dict) -> list[str]:
    categories = paper.get("categories", "")
    if not categories:
        return ["unknown"]
    cats = categories.split()
    return [cats[0]] if cats else ["unknown"]


def _is_date_folder(name: str) -> bool:
    """Check if a folder name looks like a date (YYYY-MM-DD)."""
    try:
        datetime.strptime(name, "%Y-%m-%d")
        return True
    except ValueError:
        return False


def get_raw_sources() -> list[dict]:
    """
    Get all raw papers organized by date and category.
    Reads from both legacy date-based and new domain-based structures.

    Returns:
        List of date groups, each containing category groups with papers.
    """
    if not RAW_DIR.exists():
        return []

    date_groups = {}

    # Scan all items in RAW_DIR
    for item in sorted(RAW_DIR.iterdir()):
        if not item.is_dir():
            continue

        # Case 1: Legacy date-based structure (folder name is a date)
        if _is_date_folder(item.name):
            date_str = item.name
            if date_str not in date_groups:
                date_groups[date_str] = {"date": date_str, "categories": {}, "paper_count": 0}

            for paper_file in sorted(item.glob("*.json")):
                try:
                    with open(paper_file, "r", encoding="utf-8") as f:
                        paper = json.load(f)

                    paper["filename"] = paper_file.stem
                    paper["source"] = "raw"

                    # Group by primary category
                    cats = paper.get("categories", "").split()
                    primary_cat = cats[0] if cats else "unknown"

                    if primary_cat not in date_groups[date_str]["categories"]:
                        date_groups[date_str]["categories"][primary_cat] = []

                    date_groups[date_str]["categories"][primary_cat].append(paper)
                    date_groups[date_str]["paper_count"] += 1

                except Exception as e:
                    print(f"Warning: Failed to load {paper_file}: {e}")

        # Case 2: New domain-based structure (folder name is a domain)
        elif not item.name.startswith(".") and not item.name == "__pycache__":
            domain_name = item.name.replace("_", "/")
            for date_folder in sorted(item.iterdir()):
                if not date_folder.is_dir() or not _is_date_folder(date_folder.name):
                    continue

                date_str = date_folder.name
                if date_str not in date_groups:
                    date_groups[date_str] = {"date": date_str, "categories": {}, "paper_count": 0}

                for paper_file in sorted(date_folder.glob("*.json")):
                    try:
                        with open(paper_file, "r", encoding="utf-8") as f:
                            paper = json.load(f)

                        paper["filename"] = paper_file.stem
                        paper["source"] = "raw"

                        # Use the domain folder name as category
                        if domain_name not in date_groups[date_str]["categories"]:
                            date_groups[date_str]["categories"][domain_name] = []

                        # Avoid duplicates
                        existing_ids = {p["arxiv_id"] for p in date_groups[date_str]["categories"][domain_name]}
                        if paper["arxiv_id"] not in existing_ids:
                            date_groups[date_str]["categories"][domain_name].append(paper)
                            date_groups[date_str]["paper_count"] += 1

                    except Exception as e:
                        print(f"Warning: Failed to load {paper_file}: {e}")

    # Convert to sorted list
    result = []
    for date_str in sorted(date_groups.keys(), reverse=True):
        group = date_groups[date_str]
        categories = []
        for cat_name in sorted(group["categories"].keys()):
            categories.append({
                "category": cat_name,
                "display_name": DOMAIN_DISPLAY_NAMES.get(cat_name, cat_name),
                "paper_count": len(group["categories"][cat_name]),
                "papers": group["categories"][cat_name],
            })

        result.append({
            "date": group["date"],
            "paper_count": group["paper_count"],
            "categories": categories,
        })

    return result


def get_paper_by_id(arxiv_id: str) -> Optional[dict]:
    """Find a paper by its arXiv ID across all storage structures."""
    safe_id = arxiv_id.replace("/", "_")

    # Search in all JSON files
    for json_file in RAW_DIR.rglob("*.json"):
        try:
            with open(json_file, "r", encoding="utf-8") as f:
                paper = json.load(f)
            if paper.get("arxiv_id") == arxiv_id:
                paper["filename"] = json_file.stem
                paper["source"] = "raw"
                return paper
        except Exception:
            continue

    return None


def get_domains() -> list[dict]:
    """Get all domains with metadata (for the domain-based view)."""
    if not RAW_DIR.exists():
        return []

    domains = []
    for domain_folder in sorted(RAW_DIR.iterdir()):
        if not domain_folder.is_dir():
            continue
        if _is_date_folder(domain_folder.name):
            continue

        domain_name = domain_folder.name.replace("_", "/")
        display_name = DOMAIN_DISPLAY_NAMES.get(domain_name, domain_name)

        date_folders = []
        total_papers = 0
        for date_folder in sorted(domain_folder.iterdir(), reverse=True):
            if not date_folder.is_dir():
                continue
            paper_count = len(list(date_folder.glob("*.json")))
            total_papers += paper_count
            date_folders.append({
                "date": date_folder.name,
                "paper_count": paper_count,
            })

        if total_papers > 0:
            domains.append({
                "domain": domain_name,
                "display_name": display_name,
                "paper_count": total_papers,
                "date_folders": date_folders,
            })

    return domains


def get_papers_for_domain(domain: str) -> list[dict]:
    domain_folder = _get_domain_folder(domain)
    if not domain_folder.exists():
        return []

    result = []
    for date_folder in sorted(domain_folder.iterdir(), reverse=True):
        if not date_folder.is_dir():
            continue

        papers = []
        for paper_file in sorted(date_folder.glob("*.json")):
            with open(paper_file, "r", encoding="utf-8") as f:
                paper = json.load(f)
                paper["filename"] = paper_file.stem
                papers.append(paper)

        if papers:
            result.append({
                "date": date_folder.name,
                "paper_count": len(papers),
                "papers": papers,
            })

    return result


def get_paper_detail(domain: str, date: str, paper_id: str) -> Optional[dict]:
    domain_folder = _get_domain_folder(domain)
    paper_path = domain_folder / date / f"{paper_id}.json"

    if not paper_path.exists():
        return None

    with open(paper_path, "r", encoding="utf-8") as f:
        paper = json.load(f)
        paper["filename"] = paper_path.stem
        paper["domain"] = domain
        paper["date"] = date
        return paper


def migrate_existing_papers() -> dict[str, int]:
    """Migrate papers from old date-based structure to new domain-based structure."""
    counts = {}

    if not RAW_DIR.exists():
        return counts

    for item in sorted(RAW_DIR.iterdir()):
        if not item.is_dir() or not _is_date_folder(item.name):
            continue

        date_str = item.name
        migrated = 0

        for json_file in item.glob("*.json"):
            try:
                with open(json_file, "r", encoding="utf-8") as f:
                    paper = json.load(f)

                domains = _extract_domains(paper)
                for domain in domains:
                    save_paper_by_domain(paper, domain, date_str)
                    counts[domain] = counts.get(domain, 0) + 1
                    migrated += 1

            except Exception as e:
                print(f"Warning: Failed to migrate {json_file}: {e}")

        if migrated > 0:
            print(f"Migrated {migrated} papers from {date_str}")

    return counts
