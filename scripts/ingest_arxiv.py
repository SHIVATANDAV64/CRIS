"""
Ingest arXiv Papers — Fetch and save paper metadata from arXiv.

Supports both legacy date-based storage and new domain-based storage.

Usage:
    python scripts/ingest_arxiv.py --date 2026-05-12
    python scripts/ingest_arxiv.py --days-back 3
    python scripts/ingest_arxiv.py --date 2026-05-12 --categories cs.AI,cs.CL --max 50
    python scripts/ingest_arxiv.py --domain-mode --days-back 7
    python scripts/ingest_arxiv.py --migrate
"""
import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from rich.console import Console
from core.arxiv_client import fetch_papers, save_papers, save_papers_by_domain
from core.domain_manager import migrate_existing_papers, get_domains

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
    parser.add_argument(
        "--domain-mode",
        action="store_true",
        help="Save papers organized by domain folders instead of date folders.",
    )
    parser.add_argument(
        "--migrate",
        action="store_true",
        help="Migrate existing papers from date-based to domain-based storage.",
    )
    parser.add_argument(
        "--list-domains",
        action="store_true",
        help="List all domains with paper counts.",
    )
    args = parser.parse_args()

    if args.list_domains:
        domains = get_domains()
        if not domains:
            console.print("[yellow]No domains found. Ingest some papers first.[/yellow]")
            return

        console.print(f"\n[bold cyan]=== CRIS Domains ===[/bold cyan]")
        for domain in domains:
            console.print(f"  [bold]{domain['display_name']}[/bold] ({domain['domain']})")
            console.print(f"    Papers: {domain['paper_count']}")
            for df in domain["date_folders"]:
                console.print(f"    - {df['date']}: {df['paper_count']} papers")
        return

    if args.migrate:
        console.print(f"\n[bold cyan]=== Migrating Papers to Domain-Based Storage ===[/bold cyan]")
        counts = migrate_existing_papers()
        if not counts:
            console.print("[yellow]No papers to migrate.[/yellow]")
            return

        console.print(f"\n[bold green]Migration complete![/bold green]")
        for domain, count in counts.items():
            console.print(f"  {domain}: {count} papers")
        return

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

    storage_mode = "domain-based" if args.domain_mode else "date-based"
    console.print(f"\n[bold cyan]=== CRIS Paper Ingestion ===[/bold cyan]")
    console.print(f"Storage mode: {storage_mode}")
    console.print(f"Dates: {', '.join(dates)}")
    console.print(f"Categories: {categories or 'config defaults'}")
    console.print(f"Max per category: {args.max or 'unlimited'}")

    total_papers = 0
    total_by_domain = {}

    for date_str in dates:
        console.print(f"\n[bold]-- {date_str} --[/bold]")
        papers = fetch_papers(
            from_date=date_str,
            categories=categories,
            max_papers=args.max,
        )
        if papers:
            if args.domain_mode:
                counts = save_papers_by_domain(papers)
                for domain, count in counts.items():
                    total_by_domain[domain] = total_by_domain.get(domain, 0) + count
                total_papers += len(papers)
            else:
                save_papers(papers, date_str)
                total_papers += len(papers)

    console.print(f"\n[bold green]=== Done! Total papers ingested: {total_papers} ===[/bold green]")
    if args.domain_mode and total_by_domain:
        console.print(f"\n[bold]By domain:[/bold]")
        for domain, count in total_by_domain.items():
            console.print(f"  {domain}: {count}")


if __name__ == "__main__":
    main()
