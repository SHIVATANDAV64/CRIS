"""
build_wiki.py — Builds the Karpathy-style LLM Wiki structure from existing source pages.

This script uses ACTUAL LLM calls (Amazon Bedrock) to generate proper concept page synthesis,
not mechanical regex extraction. Each concept page is written by the LLM after reading
all source pages that reference that concept.

Generates:
1. Concept pages in data/wiki/concepts/ (LLM-synthesized aggregations)
2. index.md (master catalog)
3. log.md (operation log)

Usage:
    python scripts/build_wiki.py                    # Build everything
    python scripts/build_wiki.py --concepts-only    # Only rebuild concept pages
    python scripts/build_wiki.py --index-only       # Only rebuild index + log
"""
import re
import os
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime
from collections import defaultdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WIKI_DIR = Path("data/wiki")
SOURCES_DIR = WIKI_DIR / "sources"
CONCEPTS_DIR = WIKI_DIR / "concepts"
ENTITIES_DIR = WIKI_DIR / "entities"
INDEX_PATH = WIKI_DIR / "index.md"
LOG_PATH = WIKI_DIR / "log.md"


# ── Prompt for LLM concept page synthesis ──────────────────────────────

CONCEPT_SYNTHESIS_PROMPT = """You are a research knowledge synthesizer for CRIS (Cross-Domain Research Intelligence System).

You are writing a **concept page** for the wiki. A concept page aggregates knowledge about a specific concept across multiple research papers, synthesizing how the concept appears, is used, and connects to other ideas across domains.

The concept is: **{concept_name}**

Below are excerpts from {num_papers} research paper(s) that reference this concept. Each excerpt includes the paper's core mechanism, key insight, and domain-blind abstraction.

{paper_excerpts}

---

Write a concept page using this EXACT format:

# {concept_name}

## Definition
A clear, concise definition of this concept. 2-3 sentences max.

## How It Appears Across Papers
For each paper, explain how this concept is used or referenced. Note differences in how different domains apply it.

## Cross-Domain Connections
Synthesize: What patterns emerge when you look at this concept across all the papers? Are there surprising parallels? Contradictions? Opportunities for transfer?

## Related Concepts
List other concepts from the papers that are closely related, as [[wiki-links]].

---

Rules:
- Be concise and specific. No fluff.
- Focus on SYNTHESIS — don't just list what each paper says. Find the connections.
- Use [[wiki-links]] for any concept that might have its own page.
- If only one paper references this concept, still write a useful definition and note potential cross-domain applications.
"""


def parse_source_page(filepath: Path) -> dict:
    """Parse a source page and extract structured data."""
    content = filepath.read_text(encoding="utf-8")

    # Extract frontmatter
    fm = {}
    fm_match = re.search(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
    if fm_match:
        for line in fm_match.group(1).strip().split('\n'):
            if ':' in line:
                key, val = line.split(':', 1)
                fm[key.strip()] = val.strip()

    # Extract all [[wiki-links]]
    links = re.findall(r'\[\[(.+?)\]\]', content)

    # Extract sections
    sections = {}
    current_section = None
    current_lines = []
    for line in content.split('\n'):
        heading_match = re.match(r'^##\s+(.+)', line)
        if heading_match:
            if current_section:
                sections[current_section] = '\n'.join(current_lines).strip()
            current_section = heading_match.group(1).strip()
            current_lines = []
        elif current_section:
            current_lines.append(line)
    if current_section:
        sections[current_section] = '\n'.join(current_lines).strip()

    return {
        "filepath": filepath,
        "filename": filepath.stem,
        "arxiv_id": fm.get("arxiv_id", filepath.stem),
        "title": fm.get("title", "Unknown"),
        "contribution_type": fm.get("contribution_type", ""),
        "domains": fm.get("domains", ""),
        "date": fm.get("date", ""),
        "links": links,
        "sections": sections,
        "full_content": content,
    }


def normalize_concept_name(name: str) -> str:
    """Normalize a concept name to a valid filename."""
    clean = re.sub(r'\s+', '_', name.strip())
    clean = re.sub(r'[^\w\-]', '', clean)
    return clean


def build_concept_pages_with_llm(sources: list[dict], delay: float = 3.0) -> dict:
    """Build concept pages using actual LLM synthesis via Amazon Bedrock."""
    from openai import OpenAI
    from config.settings import BEDROCK_API_KEY, BEDROCK_BASE_URL, COMPILER_MODEL

    if not BEDROCK_API_KEY:
        print("  ERROR: BEDROCK_API_KEY not set. Cannot synthesize concept pages.")
        print("  Falling back to structural-only concept pages.")
        return build_concept_pages_structural(sources)

    client = OpenAI(
        base_url=BEDROCK_BASE_URL,
        api_key=BEDROCK_API_KEY,
    )

    # Collect all concepts and which papers reference them
    concept_papers = defaultdict(list)
    for src in sources:
        for link in src["links"]:
            concept_papers[link].append(src)

    concept_pages = {}
    total = len(concept_papers)

    for i, (concept_name, papers) in enumerate(sorted(concept_papers.items()), 1):
        print(f"  [{i}/{total}] Synthesizing: {concept_name} ({len(papers)} papers)...")

        # Build paper excerpts for the prompt
        excerpts = ""
        for p in papers:
            excerpts += f"\n### Paper: {p['title']} (arXiv: {p['arxiv_id']})\n"
            excerpts += f"**Domains:** {p['domains']}\n\n"
            for section in ["Core Mechanism", "Key Insight", "Domain-Blind Abstraction"]:
                if section in p["sections"]:
                    excerpts += f"**{section}:**\n{p['sections'][section]}\n\n"

        prompt = CONCEPT_SYNTHESIS_PROMPT.format(
            concept_name=concept_name,
            num_papers=len(papers),
            paper_excerpts=excerpts,
        )

        try:
            # Use streaming since Bedrock has streaming enabled
            stream = client.chat.completions.create(
                model=COMPILER_MODEL,
                messages=[
                    {"role": "user", "content": prompt},
                ],
                max_tokens=2048,
                temperature=0.7,
                stream=True,
            )

            # Collect streamed chunks
            content_parts = []
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content_parts.append(chunk.choices[0].delta.content)

            content = "".join(content_parts)
            concept_pages[concept_name] = content.strip()
        except Exception as e:
            print(f"    ERROR: {e}")
            # Fallback: create a minimal structural page
            concept_pages[concept_name] = _build_structural_page(concept_name, papers)

        if i < total:
            time.sleep(delay)

    return concept_pages


def build_concept_pages_structural(sources: list[dict]) -> dict:
    """Fallback: build concept pages structurally (no LLM) — used when no API key."""
    concept_papers = defaultdict(list)
    for src in sources:
        for link in src["links"]:
            concept_papers[link].append(src)

    concept_pages = {}
    for concept_name, papers in sorted(concept_papers.items()):
        concept_pages[concept_name] = _build_structural_page(concept_name, papers)

    return concept_pages


def _build_structural_page(concept_name: str, papers: list[dict]) -> str:
    """Build a minimal structural concept page (no LLM)."""
    lines = [f"# {concept_name}", "", f"*Referenced by {len(papers)} paper(s).*", ""]
    lines.append("## Source Papers")
    lines.append("")
    for p in papers:
        lines.append(f"- **{p['title']}** (arXiv: {p['arxiv_id']})")
    lines.append("")
    # Related concepts
    related = set()
    for p in papers:
        for link in p["links"]:
            if link != concept_name:
                related.add(link)
    if related:
        lines.append("## Related Concepts")
        lines.append("")
        for r in sorted(related):
            lines.append(f"- [[{r}]]")
    return "\n".join(lines)


def build_index(sources: list[dict], concept_pages: dict) -> str:
    """Build the master index.md."""
    lines = []
    lines.append("# CRIS Knowledge Wiki — Index")
    lines.append("")
    lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
    lines.append("")
    lines.append(f"**Total source papers:** {len(sources)}  ")
    lines.append(f"**Total concept pages:** {len(concept_pages)}  ")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Source pages
    lines.append("## Source Pages")
    lines.append("")
    lines.append("| arXiv ID | Title | Domains | Date |")
    lines.append("|----------|-------|---------|------|")
    for s in sorted(sources, key=lambda x: x["date"], reverse=True):
        lines.append(f"| [[{s['arxiv_id']}]] | {s['title'][:60]} | {s['domains'][:40]} | {s['date']} |")
    lines.append("")

    # Concept pages
    concept_counts = defaultdict(int)
    for s in sources:
        for link in s["links"]:
            concept_counts[link] += 1

    lines.append("## Concept Pages")
    lines.append("")
    lines.append("| Concept | Referenced By |")
    lines.append("|---------|-------------|")
    for concept in sorted(concept_counts.keys()):
        count = concept_counts[concept]
        lines.append(f"| [[{concept}]] | {count} paper(s) |")
    lines.append("")
    lines.append("---")
    lines.append("*This index is auto-maintained by the CRIS wiki compiler.*")

    return "\n".join(lines)


def build_log(sources: list[dict], concept_pages: dict) -> str:
    """Build the log.md."""
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    lines = []
    lines.append("# CRIS Wiki Operations Log")
    lines.append("")
    lines.append("*Chronological record of all wiki operations.*")
    lines.append("")
    lines.append("---")
    lines.append("")
    lines.append(f"## [{now}] build | Wiki Build")
    lines.append("")
    lines.append(f"Built wiki from {len(sources)} source pages → {len(concept_pages)} concept pages.")
    lines.append("")
    lines.append("**Sources:**")
    for s in sources:
        lines.append(f"- `{s['arxiv_id']}` — {s['title'][:60]}")
    lines.append("")
    lines.append("**Concepts created:**")
    for c in sorted(concept_pages.keys()):
        lines.append(f"- `{c}`")
    lines.append("")
    lines.append("---")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Build CRIS wiki structure")
    parser.add_argument("--concepts-only", action="store_true", help="Only rebuild concept pages")
    parser.add_argument("--index-only", action="store_true", help="Only rebuild index + log")
    parser.add_argument("--no-llm", action="store_true", help="Use structural fallback instead of LLM")
    parser.add_argument("--delay", type=float, default=3.0, help="Delay between API calls (seconds)")
    args = parser.parse_args()

    print("=" * 60)
    print("CRIS Wiki Builder")
    print("=" * 60)

    # 1. Read all source pages
    print("\n[1] Reading source pages...")
    source_files = sorted(SOURCES_DIR.glob("*.md"))
    if not source_files:
        print("  ERROR: No source pages found in data/wiki/sources/")
        return

    sources = []
    for f in source_files:
        print(f"  Reading: {f.name}")
        sources.append(parse_source_page(f))
    print(f"  Found {len(sources)} source pages.")

    # 2. Build concept pages
    if not args.index_only:
        print("\n[2] Building concept pages...")
        if args.no_llm:
            print("  Using structural fallback (no LLM)...")
            concept_pages = build_concept_pages_structural(sources)
        else:
            print("  Using LLM synthesis via Amazon Bedrock...")
            concept_pages = build_concept_pages_with_llm(sources, delay=args.delay)

        print(f"  Generated {len(concept_pages)} concept pages.")

        for concept_name, content in concept_pages.items():
            fname = normalize_concept_name(concept_name) + ".md"
            outpath = CONCEPTS_DIR / fname
            outpath.write_text(content, encoding="utf-8")
            print(f"  + {fname}")
    else:
        # Just count existing concept pages
        concept_pages = {}
        for f in CONCEPTS_DIR.glob("*.md"):
            concept_pages[f.stem] = f.read_text(encoding="utf-8")

    # 3. Build index.md
    print("\n[3] Building index.md...")
    index_content = build_index(sources, concept_pages)
    INDEX_PATH.write_text(index_content, encoding="utf-8")
    print(f"  Written: {INDEX_PATH}")

    # 4. Build log.md
    print("\n[4] Building log.md...")
    log_content = build_log(sources, concept_pages)
    LOG_PATH.write_text(log_content, encoding="utf-8")
    print(f"  Written: {LOG_PATH}")

    # Summary
    print("\n" + "=" * 60)
    print("Wiki Build Complete!")
    print(f"  Source pages:  {len(sources)}")
    print(f"  Concept pages: {len(concept_pages)}")
    print(f"  Index:         {INDEX_PATH}")
    print(f"  Log:           {LOG_PATH}")
    print("=" * 60)


if __name__ == "__main__":
    main()
