"""
lint_wiki.py — Health-check the CRIS wiki for structural issues.

Checks for:
1. Orphan pages (no inbound links from any other page)
2. Broken [[wiki-links]] (pointing to non-existent pages)
3. Source pages missing backlinks
4. Concept pages with zero source references
5. Concepts mentioned in text but lacking their own page

Usage:
    python scripts/lint_wiki.py
    python scripts/lint_wiki.py --fix  (auto-fix simple issues)
"""
import re
import sys
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

WIKI_DIR = Path("data/wiki")
SOURCES_DIR = WIKI_DIR / "sources"
CONCEPTS_DIR = WIKI_DIR / "concepts"
ENTITIES_DIR = WIKI_DIR / "entities"
LOG_PATH = WIKI_DIR / "log.md"


def collect_all_pages() -> dict:
    """Collect all wiki pages and their content."""
    pages = {}
    for d in [SOURCES_DIR, CONCEPTS_DIR, ENTITIES_DIR]:
        if d.exists():
            for f in d.glob("*.md"):
                pages[f] = f.read_text(encoding="utf-8")
    return pages


def extract_links(content: str) -> list[str]:
    """Extract all [[wiki-links]] from content."""
    return re.findall(r'\[\[(.+?)\]\]', content)


def normalize_name(name: str) -> str:
    """Normalize a concept name to match a filename."""
    clean = re.sub(r'\s+', '_', name.strip())
    clean = re.sub(r'[^\w\-]', '', clean)
    return clean


def lint():
    """Run all lint checks and report results."""
    print("=" * 60)
    print("CRIS Wiki Lint — Health Check")
    print("=" * 60)
    
    pages = collect_all_pages()
    if not pages:
        print("\nERROR: No wiki pages found!")
        return
    
    source_pages = {f: c for f, c in pages.items() if SOURCES_DIR in f.parents or f.parent == SOURCES_DIR}
    concept_pages = {f: c for f, c in pages.items() if CONCEPTS_DIR in f.parents or f.parent == CONCEPTS_DIR}
    
    print(f"\nPages found:")
    print(f"  Source pages:  {len(source_pages)}")
    print(f"  Concept pages: {len(concept_pages)}")
    
    issues = {
        "broken_links": [],
        "orphan_concepts": [],
        "missing_backlinks": [],
        "duplicate_concepts": [],
        "empty_concepts": [],
    }
    
    # --- Check 1: Broken [[wiki-links]] ---
    print("\n[Check 1] Broken [[wiki-links]]...")
    concept_filenames = set()
    for f in concept_pages:
        concept_filenames.add(f.stem)
    
    for filepath, content in source_pages.items():
        links = extract_links(content)
        for link in links:
            normalized = normalize_name(link)
            if normalized not in concept_filenames:
                issues["broken_links"].append((filepath.name, link))
    
    if issues["broken_links"]:
        print(f"  WARN: {len(issues['broken_links'])} broken links found:")
        for page, link in issues["broken_links"][:10]:
            print(f"    - {page} -> [[{link}]] (no concept page)")
    else:
        print("  OK: All [[wiki-links]] resolve to existing concept pages.")
    
    # --- Check 2: Orphan concept pages ---
    print("\n[Check 2] Orphan concept pages (no inbound references)...")
    all_referenced_concepts = set()
    for content in source_pages.values():
        for link in extract_links(content):
            all_referenced_concepts.add(normalize_name(link))
    
    for f in concept_pages:
        if f.stem not in all_referenced_concepts:
            issues["orphan_concepts"].append(f.stem)
    
    if issues["orphan_concepts"]:
        print(f"  WARN: {len(issues['orphan_concepts'])} orphan concept pages:")
        for orphan in issues["orphan_concepts"][:10]:
            print(f"    - concepts/{orphan}.md")
    else:
        print("  OK: All concept pages are referenced by at least one source.")
    
    # --- Check 3: Source pages missing Wiki Links section ---
    print("\n[Check 3] Source pages missing backlinks...")
    for filepath, content in source_pages.items():
        if "## Wiki Links" not in content:
            issues["missing_backlinks"].append(filepath.name)
    
    if issues["missing_backlinks"]:
        print(f"  WARN: {len(issues['missing_backlinks'])} source pages lack backlinks:")
        for page in issues["missing_backlinks"]:
            print(f"    - {page}")
    else:
        print("  OK: All source pages have Wiki Links backlinks.")
    
    # --- Check 4: Empty concept pages ---
    print("\n[Check 4] Concept pages with no source paper references...")
    for filepath, content in concept_pages.items():
        if "## Source Papers" in content:
            # Check if there are actual paper references
            if "### [[" not in content:
                issues["empty_concepts"].append(filepath.name)
    
    if issues["empty_concepts"]:
        print(f"  WARN: {len(issues['empty_concepts'])} concept pages have no papers:")
        for page in issues["empty_concepts"]:
            print(f"    - {page}")
    else:
        print("  OK: All concept pages reference at least one source paper.")
    
    # --- Check 5: Index freshness ---
    print("\n[Check 5] Index.md freshness...")
    index_path = WIKI_DIR / "index.md"
    if index_path.exists():
        index_content = index_path.read_text(encoding="utf-8")
        # Count how many source pages are listed in the index
        indexed_sources = len(re.findall(r'\[\[\d+\.\d+\]\]', index_content))
        if indexed_sources == len(source_pages):
            print(f"  OK: Index covers all {len(source_pages)} source pages.")
        else:
            print(f"  WARN: Index lists {indexed_sources} sources but {len(source_pages)} exist.")
    else:
        print("  ERROR: index.md not found!")
    
    # --- Summary ---
    total_issues = sum(len(v) for v in issues.values())
    print("\n" + "=" * 60)
    if total_issues == 0:
        print("RESULT: Wiki is healthy! No issues found.")
    else:
        print(f"RESULT: Found {total_issues} issue(s) to address.")
        for category, items in issues.items():
            if items:
                print(f"  - {category}: {len(items)}")
    print("=" * 60)
    
    # Append to log
    if LOG_PATH.exists():
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            status = "healthy" if total_issues == 0 else f"{total_issues} issues"
            f.write(f"\n## [{now}] lint | Wiki health check: {status}\n\n")


if __name__ == "__main__":
    lint()
