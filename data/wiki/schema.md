# CRIS Wiki Schema
# This file defines the structure, conventions, and operational rules for the CRIS knowledge wiki.
# It is read by the LLM compiler before any ingest, query, or lint operation.

## Purpose

This wiki is a **persistent, compounding knowledge base** for cross-domain research intelligence.
It tracks scientific papers from arXiv, extracts their core mechanisms, and systematically
builds connections across disciplinary boundaries. The goal is to enable researchers to
discover non-obvious structural parallels between techniques in different fields.

Inspired by [Andrej Karpathy's LLM Wiki pattern](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f).

---

## Folder Structure

```
data/
├── raw/           # Original arXiv paper metadata (JSON). READ-ONLY. Never modified.
├── wiki/
│   ├── schema.md  # THIS FILE. Wiki rules and conventions.
│   ├── index.md   # Master catalog of all wiki pages, organized by type.
│   ├── log.md     # Chronological record of all operations.
│   ├── sources/   # Per-paper source summary pages (one per ingested paper).
│   ├── concepts/  # Concept pages aggregating knowledge across papers.
│   └── entities/  # Entity pages for specific models, datasets, techniques.
└── cris.db        # SQLite FTS5 search index over wiki content.
```

---

## Page Types

### Source Pages (`sources/`)
- **One per ingested paper**, named by arXiv ID (e.g., `2405.02079.md`).
- Contains: YAML frontmatter, Core Mechanism, Key Insight, Domain-Blind Abstraction,
  Cross-Domain Potential, Key Terms.
- All key terms are `[[wiki-links]]` pointing to concept or entity pages.
- **Immutable after creation** unless the source paper is updated.

### Concept Pages (`concepts/`)
- **One per recurring concept** (e.g., `Bayesian_Networks.md`, `Knowledge_Distillation.md`).
- Aggregates knowledge from ALL source pages that mention this concept.
- Contains: definition, list of papers that use/discuss this concept, cross-references
  to related concepts, and a synthesis of how the concept appears across domains.
- **Updated incrementally** every time a new source page references this concept.

### Entity Pages (`entities/`)
- **One per specific named entity** — a model, dataset, benchmark, or tool.
- Contains: description, papers that use it, related entities.

---

## Ingest Workflow

When a new paper is added:

1. **Read** the paper metadata and abstract from `raw/`.
2. **Read `index.md`** to understand what already exists in the wiki.
3. **Create** a source page in `sources/` with the standard template.
4. **For each `[[concept]]`** mentioned in the source page:
   - If a concept page exists → **update it** with the new paper's perspective.
   - If no concept page exists → **create one**.
5. **Update `index.md`** with the new/changed pages.
6. **Append to `log.md`** what was done.

---

## Naming Conventions

- Source pages: `sources/{arxiv_id}.md`
- Concept pages: `concepts/{Concept_Name}.md` (Title_Case with underscores)
- Entity pages: `entities/{Entity_Name}.md`
- All filenames use underscores, no spaces.

---

## Linking Rules

- Every `[[Term]]` in a source page MUST have a corresponding concept or entity page.
- Concept pages MUST back-link to all source pages that reference them.
- Use the format `[[Concept Name]]` which resolves to `concepts/Concept_Name.md`.

---

## Lint Rules

Periodic health checks should verify:
- No orphan pages (pages with zero inbound links)
- No broken links (links pointing to non-existent pages)
- No duplicate concept pages (same concept under different names)
- All source pages have at least 3 concept links
- Index.md is up to date
