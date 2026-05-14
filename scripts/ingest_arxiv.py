"""
Ingest arXiv Papers — Fetch and save paper metadata from arXiv.

Usage:
    python scripts/ingest_arxiv.py --date 2026-05-12
    python scripts/ingest_arxiv.py --days-back 3
    python scripts/ingest_arxiv.py --date 2026-05-12 --categories cs.AI,cs.CL --max 50
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from core.arxiv_client import fetch_papers, save_papers

console = Console()


def main():
    parser = argparse.ArgumentParser(description="Ingest papers from arXiv")
    parser.add_argument(
        "--date",
        type=str,
        help="Fetch papers from this date (YYYY-MM-DD). Defaults to yesterday.",
    )
    parser.add_argument(
        "--days-back",
        type=int,
        default=0,
        help="Fetch papers from N days ago up to today.",
    )
    parser.add_argument(
        "--categories",
        type=str,
        help="Comma-separated arXiv categories (e.g., cs.AI,cs.CL). Uses config defaults if not set.",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Maximum papers per category (for testing).",
    )
    args = parser.parse_args()

    # Determine date(s) to fetch
    if args.days_back > 0:
        dates = []
        for i in range(args.days_back, -1, -1):
            d = datetime.now() - timedelta(days=i)
            dates.append(d.strftime("%Y-%m-%d"))
    elif args.date:
        dates = [args.date]
    else:
        yesterday = datetime.now() - timedelta(days=1)
        dates = [yesterday.strftime("%Y-%m-%d")]

    # Parse categories
    categories = args.categories.split(",") if args.categories else None

    console.print(f"\n[bold cyan]=== CRIS Paper Ingestion ===[/bold cyan]")
    console.print(f"Dates: {', '.join(dates)}")
    console.print(f"Categories: {categories or 'config defaults'}")
    console.print(f"Max per category: {args.max or 'unlimited'}")

    total_papers = 0
    for date_str in dates:
        console.print(f"\n[bold]-- {date_str} --[/bold]")
        papers = fetch_papers(
            from_date=date_str,
            categories=categories,
            max_papers=args.max,
        )
        if papers:
            save_papers(papers, date_str)
            total_papers += len(papers)

    console.print(f"\n[bold green]=== Done! Total papers ingested: {total_papers} ===[/bold green]")


if __name__ == "__main__":
    main()
