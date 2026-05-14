"""
Compile Wiki Entries — Process raw paper JSONs into structured wiki entries.

Usage:
    python scripts/compile_wiki.py --date 2026-05-12
    python scripts/compile_wiki.py --all
    python scripts/compile_wiki.py --date 2026-05-12 --max 10
"""
import argparse
import json
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from config.settings import RAW_DIR, WIKI_DIR, OPENROUTER_API_KEY
from core.wiki_compiler import WikiCompiler
from core.arxiv_client import load_papers

console = Console()


def get_existing_wiki_ids() -> set:
    """Get set of arxiv IDs that already have wiki entries."""
    existing = set()
    for f in WIKI_DIR.glob("*.md"):
        # Filename is {arxiv_id}.md (with / replaced by _)
        existing.add(f.stem.replace("_", "/"))
    return existing


def save_wiki_entry(arxiv_id: str, content: str):
    """Save a wiki entry as a markdown file."""
    safe_id = arxiv_id.replace("/", "_")
    filepath = WIKI_DIR / f"{safe_id}.md"
    filepath.write_text(content, encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="Compile papers into wiki entries")
    parser.add_argument("--date", type=str, help="Compile papers from this date (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="Compile all unprocessed papers")
    parser.add_argument("--max", type=int, default=None, help="Maximum papers to compile")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between API calls (seconds)")
    args = parser.parse_args()

    # Check API key
    if not OPENROUTER_API_KEY or OPENROUTER_API_KEY == "your_openrouter_api_key_here":
        console.print("[red]Error: Set OPENROUTER_API_KEY in .env file[/red]")
        console.print("Get a free key from: https://openrouter.ai/settings/keys")
        sys.exit(1)

    console.print(f"\n[bold cyan]=== CRIS Wiki Compilation ===[/bold cyan]")

    # Gather papers to compile
    papers = []
    if args.all:
        for date_dir in sorted(RAW_DIR.iterdir()):
            if date_dir.is_dir():
                papers.extend(load_papers(date_dir.name))
    elif args.date:
        papers = load_papers(args.date)
    else:
        console.print("[red]Specify --date or --all[/red]")
        sys.exit(1)

    if not papers:
        console.print("[yellow]No papers found to compile[/yellow]")
        sys.exit(0)

    # Limit if requested
    if args.max:
        papers = papers[:args.max]

    console.print(f"Papers to process: {len(papers)}")

    # Get existing wiki entries to skip
    existing = get_existing_wiki_ids()
    console.print(f"Already compiled: {len(existing)}")

    # Initialize compiler and run
    compiler = WikiCompiler()
    results = compiler.compile_batch(
        papers,
        delay_seconds=args.delay,
        skip_existing_ids=existing,
    )

    # Save results
    saved = 0
    for arxiv_id, wiki_content in results.items():
        save_wiki_entry(arxiv_id, wiki_content)
        saved += 1

    console.print(f"\n[bold green]=== Done! Saved {saved} wiki entries to {WIKI_DIR} ===[/bold green]")


if __name__ == "__main__":
    main()
