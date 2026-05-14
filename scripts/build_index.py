"""
Build Search Index — Populate SQLite FTS5 index from wiki entries.

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

from rich.console import Console
from config.settings import WIKI_DIR, RAW_DIR, DB_PATH
from core.search_engine import create_index, add_entry, get_stats

console = Console()


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

    console.print(f"\n[bold cyan]=== CRIS Index Builder ===[/bold cyan]")

    # Rebuild if requested
    if args.rebuild and DB_PATH.exists():
        DB_PATH.unlink()
        console.print("[yellow]Deleted existing index[/yellow]")

    # Create/verify index tables
    create_index()

    # Process all wiki entries
    wiki_files = sorted(WIKI_DIR.glob("*.md"))
    console.print(f"Wiki entries found: {len(wiki_files)}")

    indexed = 0
    for wiki_file in wiki_files:
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

    # Print stats
    stats = get_stats()
    console.print(f"\n[bold green]=== Index Built ===[/bold green]")
    console.print(f"Total indexed: {stats['total_papers']}")
    console.print(f"Contribution types: {stats['contribution_types']}")


if __name__ == "__main__":
    main()
