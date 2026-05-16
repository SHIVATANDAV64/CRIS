"""
Compile Wiki Entries — Process raw paper JSONs into structured wiki entries,
then rebuild the full wiki structure (concept pages, index, log).

This follows the Karpathy LLM Wiki pattern:
1. Compile each paper into a source page (sources/{arxiv_id}.md)
2. Rebuild concept pages, index, and log using build_wiki.py

Usage:
    python scripts/compile_wiki.py --date 2026-05-12
    python scripts/compile_wiki.py --all
    python scripts/compile_wiki.py --date 2026-05-12 --max 10
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config.settings import RAW_DIR, WIKI_DIR, BEDROCK_API_KEY
from core.wiki_compiler import WikiCompiler
from core.arxiv_client import load_papers

SOURCES_DIR = WIKI_DIR / "sources"
LOG_PATH = WIKI_DIR / "log.md"


def get_existing_wiki_ids() -> set:
    """Get set of arxiv IDs that already have wiki entries in sources/."""
    existing = set()
    # Check both old location (wiki/*.md) and new (wiki/sources/*.md)
    for f in SOURCES_DIR.glob("*.md"):
        existing.add(f.stem.replace("_", "/"))
    return existing


def save_wiki_entry(arxiv_id: str, content: str):
    """Save a wiki entry as a markdown file in sources/."""
    SOURCES_DIR.mkdir(parents=True, exist_ok=True)
    safe_id = arxiv_id.replace("/", "_")
    filepath = SOURCES_DIR / f"{safe_id}.md"
    filepath.write_text(content, encoding="utf-8")


def append_to_log(message: str):
    """Append an entry to the wiki log."""
    if LOG_PATH.exists():
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            f.write(f"\n## [{now}] compile | {message}\n\n")


def main():
    parser = argparse.ArgumentParser(description="Compile papers into wiki entries")
    parser.add_argument("--date", type=str, help="Compile papers from this date (YYYY-MM-DD)")
    parser.add_argument("--all", action="store_true", help="Compile all unprocessed papers")
    parser.add_argument("--max", type=int, default=None, help="Maximum papers to compile")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between API calls (seconds)")
    parser.add_argument("--rebuild-wiki", action="store_true", default=True,
                        help="Rebuild concept pages and index after compilation (default: True)")
    args = parser.parse_args()

    # Check API key
    if not BEDROCK_API_KEY:
        print("Error: Set BEDROCK_API_KEY in .env file")
        print("Get a key from: https://console.aws.amazon.com/bedrock/")
        sys.exit(1)

    print("\n=== CRIS Wiki Compilation ===")

    # Gather papers to compile
    papers = []
    if args.all:
        for date_dir in sorted(RAW_DIR.iterdir()):
            if date_dir.is_dir():
                papers.extend(load_papers(date_dir.name))
    elif args.date:
        papers = load_papers(args.date)
    else:
        print("Specify --date or --all")
        sys.exit(1)

    if not papers:
        print("No papers found to compile")
        sys.exit(0)

    # Limit if requested
    if args.max:
        papers = papers[:args.max]

    print(f"Papers to process: {len(papers)}")

    # Get existing wiki entries to skip
    existing = get_existing_wiki_ids()
    print(f"Already compiled: {len(existing)}")

    # Initialize compiler and run
    compiler = WikiCompiler()
    results = compiler.compile_batch(
        papers,
        delay_seconds=args.delay,
        skip_existing_ids=existing,
    )

    # Save results to sources/
    saved = 0
    for arxiv_id, wiki_content in results.items():
        save_wiki_entry(arxiv_id, wiki_content)
        saved += 1

    print(f"\nSaved {saved} source pages to {SOURCES_DIR}")

    # Log the compilation
    if saved > 0:
        append_to_log(f"Compiled {saved} new source pages")

    # Rebuild full wiki structure (concept pages, index, log)
    if saved > 0 and args.rebuild_wiki:
        print("\nRebuilding wiki structure (concept pages, index)...")
        import subprocess
        result = subprocess.run(
            [sys.executable, "scripts/build_wiki.py"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(result.stdout)
        else:
            print(f"Wiki rebuild had issues:\n{result.stderr}")

    print(f"\n=== Done! ===")


if __name__ == "__main__":
    main()
