"""
Build Search Index — Populate SQLite FTS5 index from wiki source AND concept pages.

Indexes both:
- Source pages (data/wiki/sources/*.md) — per-paper summaries
- Concept pages (data/wiki/concepts/*.md) — cross-paper aggregations

Usage:
    python scripts/build_index.py
    python scripts/build_index.py --rebuild
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import WIKI_DIR, RAW_DIR, DB_PATH
from core.search_engine import create_index, add_entry, get_stats

SOURCES_DIR = WIKI_DIR / "sources"
CONCEPTS_DIR = WIKI_DIR / "concepts"


def find_paper_metadata(arxiv_id: str) -> dict:
    """Find the raw paper JSON for metadata lookup."""
    safe_id = arxiv_id.replace("/", "_")
    for date_dir in RAW_DIR.iterdir():
        if date_dir.is_dir():
            json_path = date_dir / f"{safe_id}.json"
            if json_path.exists():
                with open(json_path, "r", encoding="utf-8") as f:
                    return json.load(f)
    return {}


def main():
    parser = argparse.ArgumentParser(description="Build search index from wiki entries")
    parser.add_argument("--rebuild", action="store_true", help="Delete and rebuild index from scratch")
    args = parser.parse_args()

    print("\n=== CRIS Index Builder ===")

    # Rebuild if requested
    if args.rebuild and DB_PATH.exists():
        DB_PATH.unlink()
        print("Deleted existing index")

    # Create/verify index tables
    create_index()

    indexed = 0

    # --- Index source pages ---
    source_files = sorted(SOURCES_DIR.glob("*.md")) if SOURCES_DIR.exists() else []
    print(f"Source pages found: {len(source_files)}")

    for wiki_file in source_files:
        arxiv_id = wiki_file.stem.replace("_", "/")
        wiki_content = wiki_file.read_text(encoding="utf-8")

        # Get metadata from raw JSON
        meta = find_paper_metadata(arxiv_id)
        title = meta.get("title", arxiv_id)
        categories = meta.get("categories", "")
        date_published = meta.get("created", "")

        add_entry(
            arxiv_id=arxiv_id,
            title=title,
            wiki_content=wiki_content,
            categories=categories,
            date_published=date_published,
        )
        indexed += 1

    # --- Index concept pages ---
    concept_files = sorted(CONCEPTS_DIR.glob("*.md")) if CONCEPTS_DIR.exists() else []
    print(f"Concept pages found: {len(concept_files)}")

    for concept_file in concept_files:
        concept_name = concept_file.stem.replace("_", " ")
        content = concept_file.read_text(encoding="utf-8")

        # Use concept: prefix to distinguish from source pages
        add_entry(
            arxiv_id=f"concept:{concept_file.stem}",
            title=concept_name,
            wiki_content=content,
            categories="concept",
            date_published="",
        )
        indexed += 1

    # Print stats
    stats = get_stats()
    print(f"\n=== Index Built ===")
    print(f"Total indexed: {stats['total_papers']} ({len(source_files)} sources + {len(concept_files)} concepts)")
    print(f"Contribution types: {stats['contribution_types']}")


if __name__ == "__main__":
    main()
