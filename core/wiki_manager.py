"""
Wiki Manager — Karpathy-style Obsidian wiki with proper folder structure,
frontmatter provenance, and hierarchical summaries.

Structure:
  wiki/
  ├── sources/           # Original paper wikis (arXiv papers)
  │   └── {arxiv_id}.md
  ├── concepts/          # Aggregated concept pages (LLM-synthesized)
  │   └── {concept}.md
  ├── summaries/         # Hierarchical summaries
  │   ├── by-date/       # By month
  │   │   └── YYYY-MM.md
  │   ├── by-domain/     # By primary domain
  │   │   └── {domain}.md
  │   └── global/        # Global overview
  │       └── index.md
  ├── notes/             # Hand-written notes (user edits preserved)
  │   └── *.md
  ├── entities/          # Named entities (people, orgs, projects)
  │   └── {entity}.md
  ├── index.md           # Master catalog
  └── graph.json         # For Obsidian graph visualization
"""
import json
import re
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional
from collections import defaultdict

from rich.console import Console

console = Console()


class WikiManager:
    """Manages Karpathy-style wiki with proper structure and provenance."""

    def __init__(self, wiki_dir: Path):
        self.wiki_dir = Path(wiki_dir)
        self.sources_dir = self.wiki_dir / "sources"
        self.concepts_dir = self.wiki_dir / "concepts"
        self.summaries_dir = self.wiki_dir / "summaries"
        self.notes_dir = self.wiki_dir / "notes"
        self.entities_dir = self.wiki_dir / "entities"

        self._ensure_structure()

    def _ensure_structure(self):
        """Create proper folder structure."""
        dirs = [
            self.sources_dir,
            self.concepts_dir,
            self.summaries_dir / "by-date",
            self.summaries_dir / "by-domain",
            self.summaries_dir / "global",
            self.notes_dir,
            self.entities_dir,
        ]
        for d in dirs:
            d.mkdir(parents=True, exist_ok=True)

    def parse_frontmatter(self, content: str) -> tuple[dict, str]:
        """Parse YAML frontmatter from markdown content."""
        fm_match = re.match(r'^---\s*\n(.*?)\n---', content, re.DOTALL)
        if not fm_match:
            return {}, content

        try:
            fm = yaml.safe_load(fm_match.group(1)) or {}
        except yaml.YAMLError:
            fm = {}

        body = content[fm_match.end():].lstrip('\n')
        return fm, body

    def create_frontmatter(self, data: dict) -> str:
        """Create YAML frontmatter from data dict."""
        return "---\n" + yaml.dump(data, default_flow_style=False, sort_keys=False).strip() + "\n---"

    def write_source(self, arxiv_id: str, content: str, metadata: dict) -> Path:
        """Write a source (paper) wiki entry. Content should already include frontmatter."""
        # If content doesn't start with ---, add frontmatter
        if not content.strip().startswith("---"):
            fm = {
                "arxiv_id": arxiv_id,
                "title": metadata.get("title", ""),
                "contribution_type": metadata.get("contribution_type", "unknown"),
                "domains": metadata.get("domains", []),
                "date": metadata.get("date", ""),
                "source": "arxiv",
                "source_id": arxiv_id,
                "ingested_at": datetime.now().isoformat(),
                "scope": "paper",
                "provenance": [
                    {
                        "type": "paper",
                        "id": arxiv_id,
                        "url": f"https://arxiv.org/abs/{arxiv_id}",
                        "retrieved_at": datetime.now().isoformat()
                    }
                ]
            }
            content = self.create_frontmatter(fm) + "\n\n" + content

        out_path = self.sources_dir / f"{arxiv_id}.md"
        out_path.write_text(content, encoding="utf-8")
        return out_path

    def get_all_sources(self) -> list[dict]:
        """Get all source wiki entries with metadata."""
        sources = []
        for f in self.sources_dir.glob("*.md"):
            content = f.read_text(encoding="utf-8")
            fm, body = self.parse_frontmatter(content)

            links = re.findall(r'\[\[(.+?)\]\]', body)

            sources.append({
                "path": f,
                "arxiv_id": fm.get("arxiv_id", f.stem),
                "title": fm.get("title", ""),
                "contribution_type": fm.get("contribution_type", ""),
                "domains": fm.get("domains", []),
                "date": fm.get("date", ""),
                "links": links,
                "body": body,
            })
        return sources

    def generate_date_summaries(self, sources: list[dict]) -> dict[str, str]:
        """Generate summaries grouped by month."""
        by_month = defaultdict(list)
        for s in sources:
            date = s.get("date", "")
            date_str = str(date) if date else ""
            if date_str and "-" in date_str:
                month = date_str[:7]
                by_month[month].append(s)

        summaries = {}
        for month in sorted(by_month.keys(), reverse=True):
            papers = by_month[month]
            lines = [f"# Research Summary — {month}", ""]
            lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
            lines.append(f"**Papers this month:** {len(papers)}")
            lines.append("")

            domains = set()
            for p in papers:
                lines.append(f"## [[{p['arxiv_id']}]] — {p['title'][:60]}")
                lines.append(f"**Type:** {p['contribution_type']}")
                if p.get("domains"):
                    for d in p["domains"]:
                        domains.add(d)
                lines.append(f"**Links:** {', '.join(p['links'][:5])}")
                lines.append("")

            lines.append("## Domains Active")
            for d in sorted(domains):
                lines.append(f"- {d}")

            summaries[month] = "\n".join(lines)

            out_path = self.summaries_dir / "by-date" / f"{month}.md"
            out_path.write_text(summaries[month], encoding="utf-8")
            console.print(f"  [green]+[/green] {out_path.name}")

        return summaries

    def generate_domain_summaries(self, sources: list[dict]) -> dict[str, str]:
        """Generate summaries grouped by primary domain."""
        by_domain = defaultdict(list)
        for s in sources:
            domains = s.get("domains", [])
            if domains:
                primary = domains[0] if isinstance(domains, list) else domains.split(",")[0].strip()
                by_domain[primary].append(s)

        summaries = {}
        for domain in sorted(by_domain.keys()):
            papers = by_domain[domain]
            lines = [f"# {domain}", ""]
            lines.append(f"*Papers: {len(papers)}*")
            lines.append("")

            for p in papers:
                lines.append(f"## [[{p['arxiv_id']}]]")
                lines.append(f"**Title:** {p['title']}")
                lines.append(f"**Type:** {p['contribution_type']}")
                lines.append(f"**Date:** {str(p.get('date', 'unknown'))}")
                lines.append(f"**Key terms:** {', '.join(p['links'][:5])}")
                lines.append("")

            summaries[domain] = "\n".join(lines)

            safe_name = re.sub(r'[^\w\-]', '_', domain)
            out_path = self.summaries_dir / "by-domain" / f"{safe_name}.md"
            out_path.write_text(summaries[domain], encoding="utf-8")
            console.print(f"  [green]+[/green] {out_path.name}")

        return summaries

    def generate_global_summary(self, sources: list[dict], concept_pages: dict) -> str:
        """Generate global wiki index."""
        lines = []
        lines.append("# CRIS Knowledge Base — Global Index")
        lines.append("")
        lines.append(f"*Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")
        lines.append("")
        lines.append("---")
        lines.append("")

        lines.append(f"## Statistics")
        lines.append(f"- **Total papers:** {len(sources)}")
        lines.append(f"- **Total concepts:** {len(concept_pages)}")
        lines.append("")

        domains = set()
        types = defaultdict(int)
        for s in sources:
            if s.get("domains"):
                for d in s["domains"]:
                    domains.add(d)
            types[s.get("contribution_type", "unknown")] += 1

        lines.append(f"## Domain Coverage")
        for d in sorted(domains):
            lines.append(f"- [[{d}]]")
        lines.append("")

        lines.append(f"## Contribution Types")
        for t, c in sorted(types.items(), key=lambda x: -x[1]):
            lines.append(f"- **{t}:** {c}")
        lines.append("")

        lines.append("## Recent Papers")
        sorted_sources = sorted(sources, key=lambda x: str(x.get("date", "")), reverse=True)[:10]
        for s in sorted_sources:
            lines.append(f"- [[{s['arxiv_id']}]] — {s['title'][:50]}...")
        lines.append("")

        lines.append("---")
        lines.append("*This is your personal research knowledge graph. Edit `notes/` to add your own insights.*")

        content = "\n".join(lines)
        out_path = self.summaries_dir / "global" / "index.md"
        out_path.write_text(content, encoding="utf-8")
        console.print(f"  [green]+[/green] global/index.md")

        return content

    def build_graph_json(self, sources: list[dict], concept_pages: dict) -> dict:
        """Build graph.json for Obsidian graph view."""
        nodes = []
        edges = []

        # Map canonical ID (case-insensitive) to node metadata
        node_registry = {}

        # 1. Sources (papers)
        for s in sources:
            arxiv_id = s["arxiv_id"]
            node_registry[arxiv_id.lower()] = {
                "id": arxiv_id,
                "type": "paper",
                "label": s["title"][:40] if s.get("title") else arxiv_id,
                "domains": s.get("domains", []),
                "body": s.get("body", "")
            }

        # 2. Concepts
        for f in self.concepts_dir.glob("*.md"):
            name = f.stem
            content = f.read_text(encoding="utf-8")
            fm, body = self.parse_frontmatter(content)
            label = fm.get("title") or name
            node_registry[name.lower()] = {
                "id": name,
                "type": "concept",
                "label": label,
                "body": body
            }

        # 3. Notes
        for f in self.notes_dir.glob("*.md"):
            name = f.stem
            content = f.read_text(encoding="utf-8")
            fm, body = self.parse_frontmatter(content)
            label = fm.get("title") or name
            node_registry[name.lower()] = {
                "id": name,
                "type": "note",
                "label": label,
                "body": body
            }

        # 4. Entities
        for f in self.entities_dir.glob("*.md"):
            name = f.stem
            content = f.read_text(encoding="utf-8")
            fm, body = self.parse_frontmatter(content)
            label = fm.get("title") or name
            node_registry[name.lower()] = {
                "id": name,
                "type": "entity",
                "label": label,
                "body": body
            }

        # Register nodes list
        for canonical_lower, info in node_registry.items():
            node_dict = {
                "id": info["id"],
                "type": info["type"],
                "label": info["label"]
            }
            if "domains" in info:
                node_dict["domains"] = info["domains"]
            nodes.append(node_dict)

        # Parse links and generate edges
        seen_edges = set()
        wiki_link_re = re.compile(r'\[\[([^\]|]+)(?:\|[^\]]+)?\]\]')

        for canonical_lower, info in node_registry.items():
            body = info.get("body", "")
            links = wiki_link_re.findall(body)
            source_id = info["id"]

            for link in links:
                target_clean = link.strip()
                target_lower = target_clean.lower()

                if target_lower in node_registry:
                    target_id = node_registry[target_lower]["id"]

                    if source_id == target_id:
                        continue

                    # Represent as undirected for deduplication
                    edge_key = tuple(sorted([source_id, target_id]))
                    if edge_key not in seen_edges:
                        seen_edges.add(edge_key)
                        edges.append({
                            "source": source_id,
                            "target": target_id
                        })

        graph = {"nodes": nodes, "edges": edges}
        graph_path = self.wiki_dir / "graph.json"
        graph_path.write_text(json.dumps(graph, indent=2), encoding="utf-8")

        return graph

    def get_notes(self) -> list[Path]:
        """Get all user notes."""
        return list(self.notes_dir.glob("*.md"))

    def rebuild_all(self):
        """Rebuild entire wiki structure."""
        console.print("\n[cyan]Rebuilding wiki structure...[/cyan]")

        sources = self.get_all_sources()
        console.print(f"  Found {len(sources)} source pages")

        console.print("\n[cyan]Generating date summaries...[/cyan]")
        self.generate_date_summaries(sources)

        console.print("\n[cyan]Generating domain summaries...[/cyan]")
        self.generate_domain_summaries(sources)

        concept_files = list(self.concepts_dir.glob("*.md"))
        concept_pages = {f.stem: f.read_text() for f in concept_files}

        console.print("\n[cyan]Generating global summary...[/cyan]")
        self.generate_global_summary(sources, concept_pages)

        console.print("\n[cyan]Building graph.json...[/cyan]")
        self.build_graph_json(sources, concept_pages)

        console.print("\n[green]Wiki structure rebuilt![/green]")