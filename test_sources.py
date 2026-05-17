from core.domain_manager import get_raw_sources
sources = get_raw_sources()
total = sum(g['paper_count'] for g in sources)
print(f'Total: {total} papers across {len(sources)} dates')
for g in sources:
    print(f'  {g["date"]}: {g["paper_count"]} papers')
    for cat in g['categories']:
        print(f'    - {cat["category"]}: {cat["paper_count"]} papers')
        for p in cat['papers'][:2]:
            print(f'      {p["arxiv_id"]}: {p["title"][:60]}...')
