"""
Compile Wiki Entries for all raw papers that don't have wiki entries yet.
Uses MiniMax M2.5 via Amazon Bedrock OpenAI-compatible endpoint.

Usage:
    python scripts/compile_missing_wikis.py
    python scripts/compile_missing_wikis.py --max 10
    python scripts/compile_missing_wikis.py --delay 5
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from core.domain_manager import get_raw_sources
from core.search_engine import get_all_entries
from core.wiki_compiler import WikiCompiler
from scripts.compile_wiki import save_wiki_entry
from config.settings import BEDROCK_API_KEY
from rich.console import Console

console = Console()


def main():
    import argparse
    parser = argparse.ArgumentParser(description="Compile missing wiki entries")
    parser.add_argument("--max", type=int, default=None, help="Max papers to compile")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between API calls")
    args = parser.parse_args()

    if not BEDROCK_API_KEY:
        console.print("[red]BEDROCK_API_KEY not set in .env[/red]")
        sys.exit(1)

    # Get all raw papers
    raw_sources = get_raw_sources()
    raw_papers = {}
    for dg in raw_sources:
        for cat in dg['categories']:
            for p in cat['papers']:
                raw_papers[p['arxiv_id']] = p

    # Get all wiki entries from DB
    wiki_entries = get_all_entries()
    wiki_ids = {e['arxiv_id'] for e in wiki_entries if not e['arxiv_id'].startswith('concept:')}

    # Find missing
    missing_ids = set(raw_papers.keys()) - wiki_ids
    existing = set(raw_papers.keys()) & wiki_ids

    console.print(f"[cyan]Raw papers: {len(raw_papers)}[/cyan]")
    console.print(f"[green]Wiki entries in DB: {len(wiki_ids)}[/green]")
    console.print(f"[yellow]Missing wiki: {len(missing_ids)}[/yellow]")
    console.print(f"[dim]Already compiled: {len(existing)}[/dim]")

    if not missing_ids:
        console.print("[green]All raw papers have wiki entries![/green]")
        return

    # Build list to compile
    to_compile = [raw_papers[aid] for aid in sorted(missing_ids)]
    if args.max:
        to_compile = to_compile[:args.max]

    console.print(f"\n[yellow]Compiling {len(to_compile)} missing wikis...[/yellow]\n")

    compiler = WikiCompiler()
    results = compiler.compile_batch(to_compile, delay_seconds=args.delay)

    # Save to sources/ and add to DB
    saved = 0
    from core.search_engine import add_entry
    for arxiv_id, wiki_content in results.items():
        save_wiki_entry(arxiv_id, wiki_content)
        paper = raw_papers[arxiv_id]
        add_entry(
            arxiv_id=arxiv_id,
            title=paper['title'],
            wiki_content=wiki_content,
            categories=paper.get('categories', ''),
            date_published=paper.get('created', '')[:10],
        )
        saved += 1

    console.print(f"\n[bold green]Done! Compiled & indexed: {saved}/{len(to_compile)}[/bold green]")


if __name__ == "__main__":
    main()
