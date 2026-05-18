# CRIS Upgrade Plan — v2.0 → v3.0 (REVISED v2)

> **Cross-domain Research Intelligence System** — Revised platform upgrade plan
> **Date:** 2026-05-18
> **Status:** Revised v2 (self-hosted only, research engine first)
> **Key Changes:** 100% self-hosted (SearXNG), Vite+ UI upgrade first, Research Engine as core, then web proxy, then backend modularization

---

## Table of Contents

1. [What Changed](#1-what-changed)
2. [Revised Architecture](#2-revised-architecture)
3. [Technology Stack (Self-Hosted)](#3-technology-stack-self-hosted)
4. [Web Search — SearXNG Self-Hosted](#4-web-search--searxng-self-hosted)
5. [Phased Plan (Revised — 5 Phases)](#5-phased-plan-revised--5-phases)
6. [Database Changes](#6-database-changes)
7. [API Endpoints](#7-api-endpoints)
8. [Risk Assessment](#8-risk-assessment)

---

## 1. What Changed

| Aspect | Original | Revised v2 | Why |
|--------|---------|-----------|-----|
| Web Search | Brave + Exa + SearXNG | **SearXNG only (self-hosted)** | Zero cost, 70+ engines aggregated, no API dependency |
| Order | UI → Search → Engine | **Vite+ UI → Research Engine → Web Proxy → Backend** | Research engine IS the product |
| Cost | ~$10/month | **$0/month** | Everything self-hosted |
| Frontend | Incremental on current | **Vite+ scaffolding + DESIGN.md** | Proper toolchain from day one |
| Backend | Modularize first | **Modularize after research engine proven** | Don't refactor until architecture is stable |

---

## 2. Revised Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                    FRONTEND (Vite+ + DESIGN.md)                       │
│                                                                       │
│  Vite+ toolchain: vp dev, vp build, vp test, vp check                │
│  DESIGN.md: Linear or Cursor aesthetic from awesome-design-md        │
│                                                                       │
│  ├─ Proper markdown (marked.js + highlight.js)                       │
│  ├─ Dark/light theme toggle                                          │
│  ├─ Copy/export, keyboard shortcuts                                  │
│  ├─ Research panel (decomposition, connections, synthesis)           │
│  └─ Responsive, accessible, fast                                     │
└──────────────────────────────┬───────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────┐
│                      BACKEND (FastAPI)                                │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  RESEARCH ENGINE (The Core — Built First)                      │  │
│  │                                                                 │  │
│  │  1. Research Decomposer                                        │  │
│  │     → Takes research question                                  │  │
│  │     → Decomposes into sub-queries via LLM                      │  │
│  │     → Identifies: literature search, hypothesis gen,           │  │
│  │       method analysis, cross-domain mapping                    │  │
│  │                                                                 │  │
│  │  2. Cross-Domain Mapper                                        │  │
│  │     → Finds papers from different fields                       │  │
│  │     → Identifies mechanism analogies                           │  │
│  │     → Scores connection strength                               │  │
│  │     → Uses citation graph + semantic similarity                │  │
│  │                                                                 │  │
│  │  3. Evidence Synthesizer                                       │  │
│  │     → Aggregates findings across papers                        │  │
│  │     → Resolves contradictions                                  │  │
│  │     → Generates confidence-weighted conclusions                │  │
│  │     → Cites sources inline                                     │  │
│  │                                                                 │  │
│  │  4. Research Output Generator                                  │  │
│  │     → Literature reviews, reports, presentations               │  │
│  │     → Export to Markdown, PDF                                  │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  SEARCH PROXY (SearXNG Self-Hosted)                            │  │
│  │                                                                 │  │
│  │  Query → Expand → SearXNG (70+ engines) → Filter → Return     │  │
│  │                                                                 │  │
│  │  SearXNG aggregates:                                           │  │
│  │  ├─ Google, Bing, DuckDuckGo (general web)                     │  │
│  │  ├─ arXiv, PubMed, Semantic Scholar (academic)                 │  │
│  │  ├─ Wikipedia, Wikidata (knowledge)                            │  │
│  │  ├─ Reddit, Hacker News (community)                            │  │
│  │  └─ 60+ more engines                                           │  │
│  │                                                                 │  │
│  │  Quality Filter (local):                                       │  │
│  │  ├─ Remove AI slop farms                                       │  │
│  │  ├─ Boost recency (30/90 day windows)                          │  │
│  │  ├─ Source credibility scoring                                 │  │  │
│  │  └─ Domain reputation                                          │  │
│  └────────────────────────────────────────────────────────────────┘  │
│                                                                       │
│  ┌────────────────────────────────────────────────────────────────┐  │
│  │  Existing (keep working):                                      │  │
│  │  ├─ SQLite FTS5 (keyword search)                               │  │
│  │  ├─ Wiki system (markdown knowledge base)                      │  │
│  │  ├─ Chat sessions (SQLite)                                     │  │
│  │  ├─ Model client (Modal/Bedrock)                               │  │
│  │  └─ arXiv ingestion (Sickle)                                   │  │
│  └────────────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────────┘
                               │
┌──────────────────────────────▼───────────────────────────────────────┐
│                     SELF-HOSTED SERVICES                              │
│                                                                       │
│  ┌──────────────────┐  ┌──────────────────┐                          │
│  │  SearXNG         │  │  Redis (cache)   │                          │
│  │  (Docker)        │  │  (Docker)        │                          │
│  │  70+ search      │  │  Rate limiting,  │                          │
│  │  engines         │  │  result cache    │                          │
│  └──────────────────┘  └──────────────────┘                          │
│                                                                       │
│  External (only LLM): Modal / Bedrock for reasoning                  │
└──────────────────────────────────────────────────────────────────────┘
```

---

## 3. Technology Stack (Self-Hosted)

### 3.1 Frontend

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Toolchain | **Vite+** (`vp` CLI) | Unified dev/build/test/lint, fast HMR |
| Framework | **Start with current HTML/JS**, migrate to React later | Prove research engine first |
| Markdown | **marked.js + highlight.js** | Proper GFM + syntax highlighting |
| Design | **DESIGN.md** (Linear or Cursor from awesome-design-md) | AI-readable, consistent UI |
| State | **Current globals + proper error handling** | No framework overhead yet |

### 3.2 Backend

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | **FastAPI (keep)** | Working, async, auto-docs |
| Search | **SQLite FTS5 (keep)** | Works, don't replace until needed |
| Vector | **sentence-transformers (local, on-demand)** | No persistent vector DB yet |
| Web Search | **SearXNG (self-hosted Docker)** | 70+ engines, $0 cost, no API limits |
| Graph | **SQLite adjacency list** | Citation graph, start simple |
| PDF | **PyMuPDF (fitz)** | Fast extraction |

### 3.3 Web Search — SearXNG Only

| Component | Choice | Cost |
|-----------|--------|------|
| **SearXNG** | Self-hosted Docker | **$0** |
| Engines | Google, Bing, DuckDuckGo, arXiv, PubMed, Wikipedia, Reddit, HN, 60+ | **$0** |
| Cache | Redis (Docker) | **$0** |
| **Total monthly cost** | | **$0** |

---

## 4. Web Search — SearXNG Self-Hosted

### 4.1 Why SearXNG

- **70+ search engines** aggregated in one instance
- **Zero cost** — no API keys, no rate limits from providers
- **Privacy-first** — no user tracking, no query logging
- **Self-hosted** — full control, no vendor lock-in
- **JSON API** — returns structured results perfect for AI pipelines
- **Engines include**: Google, Bing, DuckDuckGo, arXiv, PubMed, Semantic Scholar, Wikipedia, Wikidata, Reddit, Hacker News, Stack Overflow, GitHub, and 60+ more

### 4.2 Docker Setup

```yaml
# docker-compose.yml
services:
  searxng:
    image: searxng/searxng:latest
    container_name: cris-searxng
    ports:
      - "8080:8080"
    environment:
      - SEARXNG_SECRET=$(openssl rand -hex 32)
      - SEARXNG_REDIS_URL=redis://cris-redis:6379/0
    volumes:
      - ./searxng:/etc/searxng:rw
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:alpine
    container_name: cris-redis
    ports:
      - "6379:6379"
    restart: unless-stopped
```

### 4.3 SearXNG Configuration

```yaml
# searxng/settings.yml
use_default_settings: true

search:
  formats:
    - json  # Enable JSON API for CRIS backend

engines:
  # Academic
  - name: arxiv
    engine: arxiv
    categories: general
    disabled: false
  - name: pubmed
    engine: pubmed
    categories: general
    disabled: false
  - name: semantic scholar
    engine: json_engine
    disabled: false

  # General web
  - name: google
    engine: google
    disabled: false
  - name: bing
    engine: bing
    disabled: false
  - name: duckduckgo
    engine: duckduckgo
    disabled: false

  # Knowledge
  - name: wikipedia
    engine: wikipedia
    disabled: false
  - name: wikidata
    engine: wikidata
    disabled: false

  # Community
  - name: reddit
    engine: reddit
    disabled: false
  - name: hacker news
    engine: hackernews
    disabled: false

server:
  port: 8080
  bind_address: "0.0.0.0"
  secret_key: "${SEARXNG_SECRET}"
  limiter: false  # Self-hosted, no rate limit
```

### 4.4 Python Client

```python
# core/searxng_client.py
import httpx
from typing import Optional

class SearXNGClient:
    """Self-hosted SearXNG client for multi-engine web search."""

    def __init__(self, base_url: str = "http://localhost:8080"):
        self.base_url = base_url.rstrip("/")

    async def search(
        self,
        query: str,
        categories: list[str] | None = None,
        engines: list[str] | None = None,
        time_range: str | None = None,  # "day", "week", "month", "year"
        max_results: int = 20,
    ) -> list[dict]:
        """Search across 70+ engines via SearXNG."""
        params = {
            "q": query,
            "format": "json",
            "pageno": 1,
        }
        if categories:
            params["categories"] = ",".join(categories)
        if engines:
            params["engines"] = ",".join(engines)
        if time_range:
            params["time_range"] = time_range

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}/search", params=params)
            resp.raise_for_status()
            data = resp.json()

        results = []
        for r in data.get("results", [])[:max_results]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("content", ""),
                "engine": r.get("engine", ""),
                "category": r.get("category", ""),
                "published_date": r.get("publishedDate"),
                "source": self._classify_source(r.get("url", "")),
            })

        return results

    def _classify_source(self, url: str) -> str:
        """Classify source type for credibility scoring."""
        if "arxiv.org" in url:
            return "academic"
        if "pubmed" in url or "ncbi.nlm.nih.gov" in url:
            return "academic"
        if "wikipedia.org" in url:
            return "reference"
        if "reddit.com" in url:
            return "community"
        if "news.ycombinator.com" in url:
            return "community"
        return "web"
```

### 4.5 Search Proxy with Quality Filter

```python
# core/search_proxy.py
import asyncio
from datetime import datetime, timedelta

class SearchProxy:
    """Self-hosted web search via SearXNG with quality filtering."""

    AI_SLOP_DOMAINS = {
        "contently.com", "contentstudio.io", "articlebuilder.net",
        "ezinearticles.com", "hubpages.com", "medium.com",  # optional
    }

    CREDIBILITY_SCORES = {
        "academic": 0.95,
        "reference": 0.85,
        "government": 0.90,
        "community": 0.60,
        "web": 0.50,
        "ai_slop": 0.10,
    }

    def __init__(self, searxng_url: str = "http://localhost:8080"):
        from core.searxng_client import SearXNGClient
        self.searxng = SearXNGClient(searxng_url)

    async def search(self, query: str, options: dict | None = None) -> list[dict]:
        """
        1. Expand query (synonyms, date filters)
        2. Search via SearXNG (all engines)
        3. Filter: remove AI slop, boost recency, score credibility
        4. Return sorted by combined score
        """
        options = options or {}

        # Search with time range if specified
        time_range = options.get("time_range")
        results = await self.searxng.search(
            query,
            time_range=time_range,
            max_results=options.get("max_results", 30),
        )

        # Quality filter
        filtered = []
        for r in results:
            # Skip AI slop
            domain = self._extract_domain(r["url"])
            if domain in self.AI_SLOP_DOMAINS:
                continue

            # Score credibility
            r["credibility_score"] = self.CREDIBILITY_SCORES.get(
                r.get("source", "web"), 0.5
            )

            # Score freshness
            r["freshness_score"] = self._compute_freshness(r.get("published_date"))

            # Combined score (relevance from SearXNG rank + freshness + credibility)
            rank_score = 1.0 / (60 + results.index(r))  # RRF-style
            r["combined_score"] = (
                0.4 * rank_score +
                0.3 * r["freshness_score"] +
                0.3 * r["credibility_score"]
            )
            filtered.append(r)

        return sorted(filtered, key=lambda r: r["combined_score"], reverse=True)

    def _compute_freshness(self, date_str: str | None) -> float:
        if not date_str:
            return 0.3  # Unknown date = medium freshness
        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            age_days = (datetime.now() - date).days
            if age_days <= 7:
                return 1.0
            elif age_days <= 30:
                return 0.8
            elif age_days <= 90:
                return 0.6
            elif age_days <= 365:
                return 0.4
            else:
                return 0.2
        except Exception:
            return 0.3

    def _extract_domain(self, url: str) -> str:
        from urllib.parse import urlparse
        return urlparse(url).netloc.replace("www.", "")
```

---

## 5. Phased Plan (Revised — 5 Phases)

### Phase 1: Vite+ UI Upgrade + DESIGN.md (Weeks 1-2)

**Goal:** Set up Vite+ toolchain, apply DESIGN.md design system, upgrade current UI with proper markdown, themes, shortcuts.

**Complexity:** M

**Dependencies:** None

**Tasks:**

| # | Task | Details | Est. |
|---|------|---------|------|
| 1.1 | Install Vite+ globally | `curl -fsSL https://vite.plus \| bash` or PowerShell | 0.5h |
| 1.2 | Scaffold frontend with Vite+ | `vp create` in `frontend/` directory, React+TS template | 1h |
| 1.3 | Copy DESIGN.md | Pick Linear or Cursor from awesome-design-md, drop into project root | 0.5h |
| 1.4 | Configure Vite proxy | `vite.config.ts` proxy `/api` → `http://localhost:8000` | 0.5h |
| 1.5 | Port current HTML to React components | Sidebar, ChatPanel, MessageList, InputArea — 1:1 with current UI | 6h |
| 1.6 | Add marked.js + highlight.js | Proper GFM markdown rendering with code syntax highlighting | 2h |
| 1.7 | Add copy message button | Clipboard API on each assistant message | 1h |
| 1.8 | Add export conversation | JSON + Markdown export via existing `/api/sessions/{id}/export` | 2h |
| 1.9 | Add keyboard shortcuts | Enter=send, Ctrl+N=new chat, Ctrl+E=export, Escape=close | 1h |
| 1.10 | Add dark/light theme toggle | CSS custom properties + localStorage, DESIGN.md tokens | 2h |
| 1.11 | Add loading skeletons | Replace "Loading..." with animated skeletons | 1h |
| 1.12 | Improve mobile responsiveness | Sidebar drawer, responsive input, message layout | 3h |
| 1.13 | Add search result relevance scores | Show BM25 score badge on results | 1h |
| 1.14 | Better streaming error handling | Retry logic, graceful disconnect recovery | 2h |

**Deliverables:**
- Vite+ frontend with DESIGN.md design system
- Proper markdown rendering with code highlighting
- Copy, export, shortcuts, themes, responsive layout
- All existing features preserved

**Verification Criteria:**
- [ ] `vp dev` starts frontend with HMR
- [ ] All existing chat features work identically
- [ ] Markdown renders properly (tables, code, lists, bold, italic)
- [ ] Code blocks have syntax highlighting
- [ ] Copy button works on each message
- [ ] Export downloads JSON and Markdown files
- [ ] Keyboard shortcuts work
- [ ] Dark/light theme toggles and persists
- [ ] Mobile layout works at 320px, 768px, 1024px

---

### Phase 2: Research Engine Core (Weeks 3-5)

**Goal:** Build Research Decomposer + Cross-Domain Mapper + Evidence Synthesizer — the core differentiator.

**Complexity:** XL

**Dependencies:** Phase 1 (UI stable)

**Tasks:**

| # | Task | Details | Est. |
|---|------|---------|------|
| 2.1 | Create ResearchDecomposer | `core/research/decomposer.py` — takes research question, decomposes into sub-queries via LLM | 5h |
| 2.2 | Define decomposition output | Structured: `{literature_queries, hypothesis_candidates, method_analysis_targets, cross_domain_pairs}` | 3h |
| 2.3 | Implement sub-query executor | Runs each sub-query through local search + SearXNG in parallel | 4h |
| 2.4 | Create CrossDomainMapper | `core/research/cross_domain_mapper.py` — finds papers from different fields with semantic similarity | 5h |
| 2.5 | Build mechanism analogy detector | Prompt template: "Given mechanism X in domain A, find analogous mechanisms in domain B" | 4h |
| 2.6 | Implement connection scoring | Score = semantic_similarity × domain_distance × recency_boost × credibility | 3h |
| 2.7 | Create EvidenceSynthesizer | `core/research/synthesizer.py` — aggregates findings, resolves contradictions, generates conclusions | 5h |
| 2.8 | Build contradiction resolver | When papers disagree, identify why (different methods, datasets, assumptions) | 4h |
| 2.9 | Implement confidence-weighted output | Each conclusion has confidence score based on evidence quality and quantity | 3h |
| 2.10 | Add inline citations | Every claim in synthesized output links to source paper | 3h |
| 2.11 | Create ResearchOutputGenerator | `core/research/output_generator.py` — generates literature reviews, reports, summaries | 4h |
| 2.12 | Add `/api/research/decompose` endpoint | POST: `{query, depth: "shallow"|"deep"}` → returns decomposition + initial results | 2h |
| 2.13 | Add `/api/research/synthesize` endpoint | POST: `{decomposition_id}` → returns synthesized findings with citations | 2h |
| 2.14 | Add `/api/research/connections` endpoint | POST: `{paper_id, target_domains}` → returns cross-domain connections | 2h |
| 2.15 | Build ResearchPanel (frontend) | New tab: "Research" — shows decomposition, sub-query results, connections | 6h |
| 2.16 | Add research mode toggle | Chat header toggle: "Chat" vs "Research" — research mode uses decomposer | 2h |
| 2.17 | Add WebSocket for research progress | Real-time updates as sub-queries complete | 4h |

**Deliverables:**
- Research Decomposer that breaks questions into sub-queries
- Cross-Domain Mapper that finds connections between fields
- Evidence Synthesizer that aggregates and resolves contradictions
- Research mode in chat with real-time progress
- Inline citations on all claims

**Verification Criteria:**
- [ ] Decomposer correctly breaks complex questions into sub-queries
- [ ] Cross-domain mapper finds papers from different fields with high similarity
- [ ] Evidence synthesizer identifies contradictions and explains why
- [ ] All synthesized claims have inline citations
- [ ] Research mode completes within 30 seconds for shallow depth
- [ ] WebSocket streams real-time sub-query completion

---

### Phase 3: SearXNG Web Search Proxy (Weeks 6-7)

**Goal:** Deploy SearXNG, build search proxy with quality filtering, integrate into chat and research engine.

**Complexity:** M

**Dependencies:** Phase 2 (research engine working)

**Tasks:**

| # | Task | Details | Est. |
|---|------|---------|------|
| 3.1 | Set up SearXNG Docker | Docker Compose with SearXNG + Redis, configure 70+ engines | 2h |
| 3.2 | Implement SearXNG client | `core/searxng_client.py` — search, parse JSON results | 3h |
| 3.3 | Build SearchProxy | `core/search_proxy.py` — query expansion, quality filter, recency boost | 4h |
| 3.4 | Add `/api/web/search` endpoint | Uses SearchProxy instead of current basic scraper | 2h |
| 3.5 | Integrate web search into chat | When query needs real-time data, auto-trigger SearXNG search | 3h |
| 3.6 | Add web search results to chat UI | Show web sources alongside wiki sources | 2h |
| 3.7 | Add recency filter UI | Toggle: "Include recent web results" with date range | 2h |
| 3.8 | Add source credibility badges | Show credibility score on each web result | 2h |
| 3.9 | Integrate web search into research engine | Sub-queries use SearchProxy for real-time data | 3h |
| 3.10 | Add search caching | Redis cache for repeated queries, TTL 1 hour | 2h |
| 3.11 | Write tests for SearchProxy | Unit tests for quality filter, freshness scoring, RRF merge | 3h |

**Deliverables:**
- SearXNG running locally via Docker
- Search proxy with quality filtering and recency boost
- Web search integrated into chat and research engine
- Source credibility badges and recency filter UI

**Verification Criteria:**
- [ ] SearXNG returns results from at least 5 different engines
- [ ] AI slop domains are filtered out
- [ ] Recent results are boosted in ranking
- [ ] Web search completes in < 3 seconds
- [ ] Chat responses include web sources when relevant
- [ ] Research engine sub-queries use web search for fresh data

---

### Phase 4: Backend Modularization (Weeks 8-9)

**Goal:** Split monolithic `app.py` into routers, create service layer, add proper error handling.

**Complexity:** M

**Dependencies:** Phase 3 (search proxy working)

**Tasks:**

| # | Task | Details | Est. |
|---|------|---------|------|
| 4.1 | Split `app.py` into routers | `routers/chat.py`, `routers/sessions.py`, `routers/search.py`, `routers/wiki.py`, `routers/settings.py`, `routers/web.py`, `routers/research.py` | 4h |
| 4.2 | Create service layer | `services/chat_service.py`, `services/search_service.py`, `services/wiki_service.py`, `services/research_service.py` | 4h |
| 4.3 | Add dependency injection | FastAPI `Depends()` for services, model clients, search proxy | 2h |
| 4.4 | Add global error handling | Custom exception handlers, structured error responses | 2h |
| 4.5 | Add request validation | Pydantic models for all request/response bodies | 2h |
| 4.6 | Add API documentation | OpenAPI docs with descriptions, examples, tags | 2h |
| 4.7 | Add response caching | Cache search results, wiki stats, session lists | 2h |
| 4.8 | Write integration tests | Test all API endpoints end-to-end | 4h |

**Deliverables:**
- Modular backend with routers and services
- Dependency injection for testability
- Global error handling and validation
- Full API documentation

---

### Phase 5: Semantic Search + Citation Graph + Polish (Weeks 10-12)

**Goal:** Add vector embeddings, citation graph, multi-source ingestion, research workflows, final polish.

**Complexity:** L

**Dependencies:** Phase 4 (backend modular)

**Tasks:**

| # | Task | Details | Est. |
|---|------|---------|------|
| 5.1 | Add sentence-transformers | `pip install sentence-transformers`, load `all-MiniLM-L6-v2` | 2h |
| 5.2 | Create embedding service | Generate embeddings for paper abstracts on-demand | 3h |
| 5.3 | Add embeddings to SQLite | New column `embedding_blob` in papers table | 2h |
| 5.4 | Implement hybrid search | BM25 (0.4) + cosine similarity (0.6) with RRF | 4h |
| 5.5 | Build citation graph | Parse references, build adjacency list in SQLite | 4h |
| 5.6 | Add citation analysis | Citation count, co-citation clusters, bursts | 3h |
| 5.7 | Add `/api/search/hybrid` endpoint | Keyword + semantic + hybrid modes | 2h |
| 5.8 | Add `/api/graph/citations` endpoint | Citation graph for paper | 2h |
| 5.9 | Implement Semantic Scholar client | `core/ingestion/semantic_scholar.py` | 4h |
| 5.10 | Implement PubMed client | `core/ingestion/pubmed.py` | 4h |
| 5.11 | Implement PDF parser | `core/ingestion/pdf_parser.py` with PyMuPDF | 5h |
| 5.12 | Add `/api/ingest/*` endpoints | All ingestion sources | 4h |
| 5.13 | Create research plan models | SQLAlchemy: ResearchPlan, Hypothesis, Task | 3h |
| 5.14 | Add `/api/plans/*` endpoints | Plan CRUD | 3h |
| 5.15 | Build PlanPanel + TaskBoard | Frontend for research workflows | 6h |
| 5.16 | Implement report export | Markdown + PDF via weasyprint | 4h |
| 5.17 | Add command palette | Ctrl+K: navigate, search, run research | 4h |
| 5.18 | Add conversation branching | Branch from any message | 3h |
| 5.19 | Performance optimization | Caching, connection pooling | 4h |
| 5.20 | Comprehensive testing | Unit + integration + E2E | 8h |

---

## 6. Database Changes

```sql
-- Citation Graph
CREATE TABLE citations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    citing_paper TEXT NOT NULL,
    cited_paper TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(citing_paper, cited_paper)
);

-- Search Results Cache (Redis-backed, SQLite fallback)
CREATE TABLE search_cache (
    id TEXT PRIMARY KEY,
    query TEXT NOT NULL,
    query_hash TEXT NOT NULL,
    results TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    UNIQUE(query_hash)
);

-- Research Plans
CREATE TABLE research_plans (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Hypotheses
CREATE TABLE hypotheses (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES research_plans(id) ON DELETE CASCADE,
    statement TEXT NOT NULL,
    status TEXT DEFAULT 'proposed',
    evidence TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES research_plans(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    status TEXT DEFAULT 'pending',
    assigned_agent TEXT,
    result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Paper embeddings
ALTER TABLE papers ADD COLUMN embedding_blob BLOB;
ALTER TABLE papers ADD COLUMN embedding_model TEXT DEFAULT 'all-MiniLM-L6-v2';
```

---

## 7. API Endpoints

### New Endpoints

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/web/search` | Multi-source web search via SearXNG proxy |
| POST | `/api/research/decompose` | Decompose research question |
| POST | `/api/research/synthesize` | Synthesize findings |
| POST | `/api/research/connections` | Find cross-domain connections |
| GET | `/api/graph/citations` | Citation graph for paper |
| POST | `/api/search/hybrid` | Hybrid search (keyword + semantic) |
| GET/POST | `/api/plans` | Research plan CRUD |
| POST | `/api/ingest/semantic-scholar` | Ingest from Semantic Scholar |
| POST | `/api/ingest/pubmed` | Ingest from PubMed |
| POST | `/api/ingest/pdf` | Upload and parse PDF |

### Existing (unchanged)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/chat/stream` | Streaming chat (SSE) |
| GET/POST | `/api/sessions` | Session CRUD |
| GET | `/api/raw-sources` | Browse papers |
| GET | `/api/wiki/*` | Wiki endpoints |
| GET/POST | `/api/settings` | Settings |

---

## 8. Risk Assessment

| Risk | Probability | Impact | Mitigation |
|------|------------|--------|------------|
| SearXNG instance goes down | Low | High | Docker restart policy, health checks |
| SearXNG rate-limited by upstream engines | Medium | Medium | Redis caching, request throttling |
| Research decomposer produces irrelevant sub-queries | Medium | High | Iterative prompt refinement, user feedback |
| Cross-domain mapper finds false connections | High | Medium | Confidence scoring, human validation |
| LLM costs explode with research mode | Medium | High | Cache results, limit depth, cheaper models |
| Vite+ migration breaks existing features | Low | Medium | Test thoroughly, keep backward compat |
| SQLite doesn't scale with embeddings | Medium | Low | Migrate to ChromaDB later if needed |

---

## Implementation Order

```
Weeks 1-2:   Phase 1 — Vite+ UI + DESIGN.md + Quick Wins
Weeks 3-5:   Phase 2 — Research Engine (Core Differentiator)
Weeks 6-7:   Phase 3 — SearXNG Web Search Proxy
Weeks 8-9:   Phase 4 — Backend Modularization
Weeks 10-12: Phase 5 — Semantic Search + Citation Graph + Polish
```

**Total: 12 weeks single developer, 8 weeks for 2 developers**
**Total cost: $0/month (all self-hosted, only LLM API costs)**
