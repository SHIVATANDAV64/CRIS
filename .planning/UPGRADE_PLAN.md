# CRIS Upgrade Plan — v2.0 → v3.0

> **Cross-domain Research Intelligence System** — Full platform upgrade plan
> **Date:** 2026-05-18
> **Status:** Proposed
> **Author:** Architecture Agent

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Technology Stack Decisions](#2-technology-stack-decisions)
3. [Phased Implementation Plan](#3-phased-implementation-plan)
4. [Database Schema Changes](#4-database-schema-changes)
5. [API Endpoint Design](#5-api-endpoint-design)
6. [Frontend Component Tree](#6-frontend-component-tree)
7. [Agent Architecture](#7-agent-architecture)
8. [Migration Strategy](#8-migration-strategy)
9. [Risk Assessment](#9-risk-assessment)
10. [Quick Wins](#10-quick-wins)

---

## 1. Architecture Overview

### 1.1 Current Architecture (v2.0)

```
┌──────────────┐     ┌──────────────────┐     ┌──────────────┐
│  arXiv OAI   │────▶│  Wiki Compiler    │────▶│  SQLite FTS5 │
│  (Sickle)    │     │  (Bedrock LLM)    │     │  Search      │
└──────────────┘     └──────────────────┘     └──────┬───────┘
                                                      │
┌──────────────┐     ┌──────────────────┐     ┌──────▼───────┐
│  HTML/JS UI  │◀───▶│  FastAPI Server   │◀───▶│  ModelClient │
│  (Vanilla)   │     │  (app.py)         │     │  (Modal/     │
└──────────────┘     └──────────────────┘     │   Bedrock)   │
                                              └──────────────┘
```

**Problems:**
- Single monolithic `app.py` (725 lines) with all routes inline
- No semantic search — only BM25 keyword matching
- No agent system — single LLM call per request
- No research workflow — no plans, tasks, hypotheses
- No knowledge graph — just markdown files on disk
- No multi-source ingestion — only arXiv OAI-PMH
- Vanilla JS frontend — no component model, no state management
- No tool use or code execution

### 1.2 Target Architecture (v3.0)

```
┌─────────────────────────────────────────────────────────────────────┐
│                        FRONTEND (React + TS + Vite)                 │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐ │
│  │ ChatPanel│ │Research  │ │Knowledge │ │TaskPanel │ │Settings  │ │
│  │          │ │Panel     │ │Graph     │ │          │ │Panel     │ │
│  └────┬─────┘ └────┬─────┘ └────┬─────┘ └────┬─────┘ └──────────┘ │
│       │             │             │             │                    │
│  ┌────▼─────────────▼─────────────▼─────────────▼──────────────────┐ │
│  │                    Zustand State Store                           │ │
│  │  (sessions, messages, papers, agents, tasks, research plans)    │ │
│  └────────────────────────────┬────────────────────────────────────┘ │
│                               │ WebSocket + REST                     │
└───────────────────────────────┼─────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                      BACKEND (FastAPI + Python)                      │
│  ┌────────────┐ ┌────────────┐ ┌────────────┐ ┌──────────────────┐ │
│  │ API Gateway│ │ Agent      │ │ Workflow   │ │ Ingestion        │ │
│  │ (routers)  │ │ Orchestrator│ │ Engine     │ │ Pipeline         │ │
│  └─────┬──────┘ └─────┬──────┘ └─────┬──────┘ └────────┬─────────┘ │
│        │               │               │                 │            │
│  ┌─────▼───────────────▼───────────────▼─────────────────▼────────┐ │
│  │                    Core Services Layer                          │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │ │
│  │  │Semantic  │ │Knowledge │ │Chat      │ │Tool             │  │ │
│  │  │Search    │ │Graph     │ │Service   │ │Executor         │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │ │
│  └────────────────────────────┬───────────────────────────────────┘ │
│                               │                                      │
│  ┌────────────────────────────▼───────────────────────────────────┐ │
│  │                    Data Layer                                   │ │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────────────┐  │ │
│  │  │SQLite    │ │ChromaDB  │ │Wiki Files│ │File Store        │  │ │
│  │  │(sessions)│ │(vectors) │ │(markdown)│ │(PDFs, uploads)   │  │ │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────────────┘  │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
                                │
┌───────────────────────────────▼─────────────────────────────────────┐
│                     EXTERNAL SERVICES                                │
│  ┌──────────┐ ┌──────────────┐ ┌──────────┐ ┌──────────────────┐   │
│  │arXiv API │ │Semantic      │ │PubMed    │ │Modal / Bedrock   │   │
│  │v2 + OAI  │ │Scholar API   │ │API       │ │LLM Providers     │   │
│  └──────────┘ └──────────────┘ └──────────┘ └──────────────────┘   │
└─────────────────────────────────────────────────────────────────────┘
```

### 1.3 Key Architectural Changes

| Aspect | v2.0 | v3.0 |
|--------|------|------|
| Frontend | Vanilla HTML/JS | React 19 + TypeScript + Vite |
| State | Global JS variables | Zustand store + React Query |
| Backend | Single `app.py` | Modular routers + service layer |
| Search | SQLite FTS5 (BM25) | Hybrid: FTS5 + ChromaDB (vectors) |
| Knowledge | Markdown files | Markdown + Knowledge Graph (NetworkX) |
| Agents | None | 6-agent swarm with coordinator |
| Workflow | None | Research plans, hypotheses, tasks |
| Ingestion | arXiv OAI-PMH only | arXiv v2 + Semantic Scholar + PubMed + PDF |
| Real-time | SSE streaming | SSE + WebSocket for agent events |
| Tools | None | Code execution sandbox, visualization |

---

## 2. Technology Stack Decisions

### 2.1 Frontend

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | **React 19** | Component model, ecosystem, team familiarity |
| Language | **TypeScript 5.x** | Type safety, better refactoring, fewer runtime errors |
| Build Tool | **Vite 6** | Fast HMR, small bundle, excellent DX |
| State Management | **Zustand** | Minimal boilerplate, no providers, perfect for this scale |
| Server State | **TanStack Query (React Query)** | Caching, deduplication, background refetch |
| Routing | **TanStack Router** | Type-safe routing, file-based routing option |
| Markdown Rendering | **react-markdown + remark-gfm + rehype-highlight** | GFM support, syntax highlighting, safe rendering |
| UI Components | **shadcn/ui + Tailwind CSS v4** | Accessible, customizable, design tokens |
| Knowledge Graph Viz | **react-force-graph-2d** | Interactive force-directed graph, lightweight |
| Code Execution | **Monaco Editor** | VS Code editor in browser, syntax highlighting |
| Drag & Drop | **@dnd-kit/core** | Modern, accessible, React-native DnD |

### 2.2 Backend

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Framework | **FastAPI (keep)** | Already working, async, auto-docs, type-safe |
| Structure | **Router-based** (split `app.py`) | Separation of concerns, testable |
| Vector DB | **ChromaDB (embedded)** | Zero-config, in-process, no external service, Python-native |
| Knowledge Graph | **NetworkX** | Pure Python, no external deps, easy serialization |
| Task Queue | **asyncio + in-process queue** | No Redis needed at this scale; upgrade later |
| PDF Parsing | **PyMuPDF (fitz)** | Fast, accurate text extraction, table support |
| BibTeX | **bibtexparser** | Standard library, reliable parsing |

### 2.3 Database

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Relational | **SQLite (keep)** | Zero-config, already in use, sufficient for single-user |
| Vector | **ChromaDB (embedded)** | Co-located with app, no network overhead |
| Migration | **Alembic** | Standard SQLAlchemy migration tool |
| ORM | **SQLAlchemy 2.0** | Type-safe queries, migration support |

### 2.4 Embeddings

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Model | **sentence-transformers/all-MiniLM-L6-v2** | 384-dim, fast, good quality, 80MB |
| Runtime | **ONNX Runtime** | CPU-optimized, no GPU needed |
| Fallback | **OpenAI embeddings API** | If local model unavailable |

---

## 3. Phased Implementation Plan

### Phase 1: Foundation & Frontend Migration (Weeks 1-3)

**Goal:** Migrate from vanilla HTML/JS to React + TypeScript while preserving all existing functionality. No new features — just architectural improvement.

**Complexity:** XL

**Dependencies:** None (first phase)

#### Tasks

| # | Task | Details | Est. |
|---|------|---------|------|
| 1.1 | Scaffold Vite + React + TS project | `npm create vite@latest frontend -- --template react-ts`. Configure Tailwind v4, shadcn/ui, TypeScript strict mode. | 2h |
| 1.2 | Create Zustand store | `stores/chatStore.ts` with sessions, messages, currentSession, loading state. Migrate from global JS variables. | 3h |
| 1.3 | Build Sidebar component | `components/sidebar/Sidebar.tsx` with tabs: History, Memory, Sources, Settings. Use shadcn Tabs + ScrollArea. | 4h |
| 1.4 | Build ChatPanel component | `components/chat/ChatPanel.tsx` with message list, input area, streaming support. Replace vanilla DOM manipulation. | 6h |
| 1.5 | Implement markdown rendering | Install `react-markdown`, `remark-gfm`, `rehype-highlight`. Create `components/chat/MarkdownRenderer.tsx` with code highlighting, tables, task lists. | 3h |
| 1.6 | Migrate SSE streaming | Rewrite `sendMessage()` to use React hooks. Use `useRef` for reader, `useState` for content accumulation. Preserve thinking/sources display. | 4h |
| 1.7 | Build SessionList component | `components/sidebar/SessionList.tsx` with create, load, delete, rename. Connect to existing `/api/sessions` endpoints. | 3h |
| 1.8 | Build SettingsPanel component | `components/sidebar/SettingsPanel.tsx` with form sections for arXiv, model, chat, search config. Connect to `/api/settings`. | 3h |
| 1.9 | Build MemoryPanel component | `components/sidebar/MemoryPanel.tsx` showing wiki stats, entities, notes. Connect to `/api/wiki/*` endpoints. | 3h |
| 1.10 | Build SourcesBrowser component | `components/sidebar/SourcesBrowser.tsx` with domain/category/paper hierarchy. Preserve drag-drop functionality using `@dnd-kit`. | 5h |
| 1.11 | Build PaperDetailModal | `components/papers/PaperDetailModal.tsx` as a dialog (shadcn Dialog). Show paper metadata, abstract, categories. | 3h |
| 1.12 | Build WebSearchPanel | `components/chat/WebSearchPanel.tsx` as collapsible panel above chat input. Connect to `/api/web/*`. | 2h |
| 1.13 | Configure Vite proxy | `vite.config.ts` proxy `/api` → `http://localhost:8000` for dev. Keep FastAPI serving API, Vite serving frontend. | 1h |
| 1.14 | Preserve drag-drop paper reference | Implement `onDragStart`/`onDrop` for paper chips above input. Store in Zustand store, send as `source_papers` in chat request. | 3h |
| 1.15 | Add keyboard shortcuts | `useEffect` listener for Enter (send), Ctrl+K (command palette placeholder), Ctrl+N (new chat). | 2h |
| 1.16 | Responsive layout | CSS media queries for mobile: sidebar as drawer, single-column chat. Test at 320px, 768px, 1024px. | 3h |
| 1.17 | Dark/light theme toggle | Use Tailwind `dark:` variant + Zustand theme store. Persist preference in localStorage. | 2h |
| 1.18 | Error boundaries & loading states | Wrap app in React ErrorBoundary. Add loading skeletons for all async data fetches. | 2h |

**Deliverables:**
- `frontend/` directory with complete React app
- All v2.0 features working identically in new frontend
- FastAPI backend unchanged (serves API only)
- `server/templates/index.html` replaced by Vite build output in production

**Verification Criteria:**
- [ ] All existing API endpoints work with new frontend
- [ ] Chat streaming works with thinking trace display
- [ ] Session CRUD (create, load, delete, rename) works
- [ ] Paper drag-drop to chat input works
- [ ] Settings save/load works
- [ ] Memory panel shows wiki stats
- [ ] Sources browser shows domain/paper hierarchy
- [ ] Web search panel works
- [ ] Responsive on mobile (sidebar collapses to drawer)
- [ ] Dark/light theme toggle persists
- [ ] No console errors in production build

---

### Phase 2: Semantic Search & Vector Embeddings (Weeks 4-5)

**Goal:** Add vector-based semantic search alongside existing BM25. Enable cross-domain queries using different vocabulary.

**Complexity:** L

**Dependencies:** Phase 1 (frontend must be stable)

#### Tasks

| # | Task | Details | Est. |
|---|------|---------|------|
| 2.1 | Add ChromaDB dependency | `pip install chromadb sentence-transformers`. Create `core/vector_store.py` with ChromaDB client wrapper. | 2h |
| 2.2 | Create embedding service | `core/embedding_service.py` with `EmbeddingService` class. Load `all-MiniLM-L6-v2` via sentence-transformers. Support batch encoding. | 3h |
| 2.3 | Create vector collection | Initialize ChromaDB collection `papers` with metadata: `arxiv_id`, `title`, `domains`, `categories`, `date_published`. | 2h |
| 2.4 | Backfill existing papers | Script `scripts/embed_papers.py` that reads all wiki entries, generates embeddings, upserts into ChromaDB. Progress bar with `rich`. | 4h |
| 2.5 | Implement hybrid search | `core/search_engine.py` → add `hybrid_search(query, limit)` that combines BM25 (weight 0.4) + vector similarity (weight 0.6) with RRF reranking. | 5h |
| 2.6 | Add `/api/search/semantic` endpoint | POST endpoint accepting `{query, limit, mode: "keyword"|"semantic"|"hybrid"}`. Return results with relevance scores. | 2h |
| 2.7 | Update chat context retrieval | Modify chat endpoint to use `hybrid_search` instead of pure BM25. Pass relevance scores to prompt. | 2h |
| 2.8 | Add search mode UI | Add toggle in frontend search bar: Keyword / Semantic / Hybrid. Default to Hybrid. | 2h |
| 2.9 | Add embedding on paper ingestion | Modify `scripts/compile_wiki.py` to generate and store embedding when a new paper wiki is compiled. | 2h |
| 2.10 | Add search analytics endpoint | `GET /api/search/stats` returning query distribution, result counts, mode usage. | 1h |

**Deliverables:**
- ChromaDB vector store with all existing papers embedded
- Hybrid search endpoint with RRF reranking
- Frontend search mode toggle
- Automatic embedding on new paper ingestion

**Verification Criteria:**
- [ ] `hybrid_search("attention mechanisms")` returns papers about transformers even if they don't use the word "attention"
- [ ] Cross-domain query "how does feedback control apply to neural networks" returns relevant papers from both control theory and ML domains
- [ ] Search results show relevance score breakdown (BM25 vs vector)
- [ ] Backfill script processes all existing papers without errors
- [ ] New paper ingestion automatically generates embedding
- [ ] Search performance < 200ms for hybrid search on 1000 papers

---

### Phase 3: Knowledge Graph & Cross-Domain Discovery (Weeks 6-7)

**Goal:** Build a knowledge graph from wiki entries, enable graph-based reasoning and cross-domain connection discovery.

**Complexity:** L

**Dependencies:** Phase 2 (vector search provides entity linking)

#### Tasks

| # | Task | Details | Est. |
|---|------|---------|------|
| 3.1 | Add NetworkX dependency | `pip install networkx`. Create `core/knowledge_graph.py` with `KnowledgeGraph` class. | 2h |
| 3.2 | Build graph from wiki entries | Parse all wiki markdown files, extract `[[wiki-links]]`, create nodes (papers, concepts, entities) and edges (references, co-occurrence). | 4h |
| 3.3 | Add concept clustering | Use vector embeddings to cluster papers by semantic similarity. Assign cluster labels. Store as node attributes. | 3h |
| 3.4 | Implement cross-domain edge detection | For each pair of papers from different domains, compute embedding similarity. If > 0.7, create `cross_domain` edge with similarity score. | 4h |
| 3.5 | Add graph traversal queries | `find_path(concept_a, concept_b)`, `get_related_concepts(paper_id, depth=2)`, `get_domain_bridge_papers(domain_a, domain_b)`. | 5h |
| 3.6 | Create `/api/graph/*` endpoints | `GET /api/graph/nodes`, `GET /api/graph/edges`, `POST /api/graph/path`, `GET /api/graph/bridges/{domain_a}/{domain_b}`. | 3h |
| 3.7 | Build KnowledgeGraphPanel (frontend) | `components/graph/KnowledgeGraphPanel.tsx` using `react-force-graph-2d`. Nodes colored by domain, edges by type. Click to show paper detail. | 6h |
| 3.8 | Add cross-domain discovery endpoint | `POST /api/discover/connections` accepting `{paper_id, limit}`. Returns papers from other domains with high semantic similarity + explanation. | 3h |
| 3.9 | Build analogy generation prompt | Create prompt template in `config/prompts.py` for generating analogies between mechanisms from different domains. | 2h |
| 3.10 | Add `/api/discover/analogies` endpoint | POST endpoint using analogy prompt. Returns structured analogies: `{source_mechanism, target_domain, analogy_explanation, confidence}`. | 2h |
| 3.11 | Add graph rebuild script | `scripts/rebuild_graph.py` that re-parses all wiki files and rebuilds the graph. Run on wiki changes. | 2h |
| 3.12 | Add graph persistence | Serialize graph to JSON on changes, load on startup. Use `networkx.readwrite.json_graph`. | 2h |

**Deliverables:**
- Knowledge graph with paper, concept, and entity nodes
- Cross-domain edge detection based on semantic similarity
- Interactive knowledge graph visualization in frontend
- Cross-domain discovery and analogy generation endpoints

**Verification Criteria:**
- [ ] Graph loads all wiki entries with correct node types
- [ ] `find_path("transformer", "gene regulation")` returns a valid path
- [ ] Knowledge graph visualization renders with correct node colors by domain
- [ ] Clicking a node shows paper/concept detail in sidebar
- [ ] Cross-domain discovery returns papers from different domains with explanations
- [ ] Analogy generation produces meaningful cross-domain analogies
- [ ] Graph rebuild script completes in < 30s for 500 papers

---

### Phase 4: Research Agent Swarm (Weeks 8-10)

**Goal:** Implement multi-agent research system with 6 specialized agents coordinated by a swarm orchestrator.

**Complexity:** XL

**Dependencies:** Phase 2 (semantic search), Phase 3 (knowledge graph)

#### Tasks

| # | Task | Details | Est. |
|---|------|---------|------|
| 4.1 | Create agent base class | `core/agents/base.py` with `BaseAgent` abstract class: `name`, `system_prompt`, `run(query, context) → AgentResult`. | 3h |
| 4.2 | Implement LiteratureReviewerAgent | `core/agents/literature_reviewer.py`. Searches papers, synthesizes summary, identifies gaps. Uses hybrid search + LLM summarization. | 4h |
| 4.3 | Implement MethodologyAnalystAgent | `core/agents/methodology_analyst.py`. Analyzes research methods, compares approaches, identifies strengths/weaknesses. | 4h |
| 4.4 | Implement CrossDomainConnectorAgent | `core/agents/cross_domain_connector.py`. Uses knowledge graph to find connections between disparate fields. Generates bridge explanations. | 5h |
| 4.5 | Implement FactCheckerAgent | `core/agents/fact_checker.py`. Verifies claims against source papers. Returns `{claim, verified, evidence, confidence}`. | 4h |
| 4.6 | Implement ResearchPlannerAgent | `core/agents/research_planner.py`. Creates research plans with milestones, hypotheses, and suggested experiments. | 4h |
| 4.7 | Implement SwarmCoordinator | `core/agents/swarm_coordinator.py`. Orchestrates agents: receives research query, decomposes into sub-tasks, dispatches to agents, combines results. Uses consensus for conflicting outputs. | 6h |
| 4.8 | Create agent registry | `core/agents/registry.py` with `AgentRegistry` class. Register, list, and retrieve agents by name/type. | 2h |
| 4.9 | Add `/api/agents/*` endpoints | `GET /api/agents` (list), `POST /api/agents/{name}/run` (run single agent), `POST /api/agents/swarm` (run swarm). | 3h |
| 4.10 | Add WebSocket for agent events | `WebSocket /ws/agents` for real-time agent progress: `{agent, status, progress, result}`. Use FastAPI WebSocket. | 4h |
| 4.11 | Build AgentPanel (frontend) | `components/agents/AgentPanel.tsx` showing available agents, run button, live progress via WebSocket, combined results. | 6h |
| 4.12 | Build ResearchMode toggle | Add "Research Mode" toggle in chat header. When enabled, queries go through swarm coordinator instead of direct chat. | 3h |
| 4.13 | Implement agent result caching | Cache agent results by query hash. TTL 24h. Use SQLite `agent_results` table. | 3h |
| 4.14 | Add agent configuration UI | Settings panel section for agent parameters: max papers per agent, consensus threshold, timeout. | 3h |
| 4.15 | Implement parallel agent execution | Use `asyncio.gather()` to run independent agents in parallel. Swarm coordinator dispatches non-dependent agents concurrently. | 4h |

**Deliverables:**
- 6 specialized research agents with distinct system prompts
- Swarm coordinator that decomposes queries and combines results
- WebSocket real-time agent progress streaming
- Frontend agent panel with live progress visualization
- Research mode toggle in chat

**Verification Criteria:**
- [ ] Each agent produces distinct, specialized output for the same query
- [ ] Swarm coordinator correctly decomposes a complex query into sub-tasks
- [ ] Parallel agents execute concurrently (verify with timing)
- [ ] WebSocket streams real-time progress updates to frontend
- [ ] Agent results are cached and reused for identical queries
- [ ] Fact checker correctly identifies unsupported claims
- [ ] Cross-domain connector finds non-obvious connections between fields
- [ ] Research planner generates actionable plans with milestones

---

### Phase 5: Research Workflow Engine (Weeks 11-12)

**Goal:** Enable users to create research plans, track hypotheses, manage tasks, and export research reports.

**Complexity:** L

**Dependencies:** Phase 4 (agent swarm)

#### Tasks

| # | Task | Details | Est. |
|---|------|---------|------|
| 5.1 | Create research plan models | `core/models/research_plan.py` with SQLAlchemy models: `ResearchPlan`, `Hypothesis`, `Milestone`, `Task`. | 3h |
| 5.2 | Add Alembic migration | `alembic revision --autogenerate` for new tables. Include indexes on foreign keys. | 1h |
| 5.3 | Implement plan CRUD service | `core/services/plan_service.py` with create, update, delete, list, get operations. | 4h |
| 5.4 | Add `/api/plans/*` endpoints | `GET/POST /api/plans`, `GET/PATCH/DELETE /api/plans/{id}`, `POST /api/plans/{id}/hypotheses`, `POST /api/plans/{id}/milestones`. | 3h |
| 5.5 | Implement task tracking | Tasks within plans: `{id, plan_id, title, status, assigned_agent, result, created_at, completed_at}`. | 3h |
| 5.6 | Add `/api/tasks/*` endpoints | CRUD for tasks within plans. Support status transitions: `pending → in_progress → completed/failed`. | 2h |
| 5.7 | Build PlanPanel (frontend) | `components/plans/PlanPanel.tsx` with plan list, detail view, hypothesis editor, milestone timeline. | 6h |
| 5.8 | Build TaskBoard component | `components/plans/TaskBoard.tsx` with Kanban-style columns: Pending, In Progress, Completed. Drag to change status. | 4h |
| 5.9 | Implement paper comparison matrix | `POST /api/compare/papers` accepting `{paper_ids, dimensions}`. Returns comparison table with LLM-generated analysis per dimension. | 4h |
| 5.10 | Build PaperComparison component | `components/compare/PaperComparison.tsx` with sortable table, side-by-side abstract view, dimension filters. | 4h |
| 5.11 | Implement report export | `POST /api/plans/{id}/export` generating Markdown and PDF reports. Use `markdown` + `weasyprint` for PDF. | 4h |
| 5.12 | Add literature review generation | `POST /api/plans/{id}/literature-review` using LiteratureReviewerAgent to generate structured literature review section. | 3h |
| 5.13 | Build ExportPanel (frontend) | `components/plans/ExportPanel.tsx` with export format selector (Markdown, PDF, JSON), preview, download button. | 3h |
| 5.14 | Add plan templates | Pre-built templates: "Literature Review", "Methodology Comparison", "Cross-Domain Analysis", "Hypothesis Testing". | 2h |

**Deliverables:**
- Research plan CRUD with hypotheses and milestones
- Task tracking with Kanban board
- Paper comparison matrix
- Research report export (Markdown + PDF)
- Plan templates for common research workflows

**Verification Criteria:**
- [ ] Create a research plan with 3 hypotheses and 5 milestones
- [ ] Tasks transition correctly through status workflow
- [ ] Paper comparison generates meaningful analysis across dimensions
- [ ] Report export produces well-formatted Markdown and PDF
- [ ] Literature review generation produces structured output with citations
- [ ] Plan templates pre-populate with appropriate structure
- [ ] All data persists across server restarts

---

### Phase 6: Multi-Source Ingestion (Weeks 13-14)

**Goal:** Expand paper ingestion beyond arXiv to include Semantic Scholar, PubMed, PDF upload, URL scraping, BibTeX import, and manual entry.

**Complexity:** L

**Dependencies:** Phase 2 (vector embeddings for all sources)

#### Tasks

| # | Task | Details | Est. |
|---|------|---------|------|
| 6.1 | Create unified paper model | `core/models/paper.py` with `Paper` class: `id`, `title`, `abstract`, `authors`, `source`, `source_id`, `url`, `pdf_path`, `domains`, `published_date`, `embedding_id`. | 2h |
| 6.2 | Implement Semantic Scholar client | `core/ingestion/semantic_scholar.py` using their free API. Search, fetch paper details, extract metadata. Rate limit aware. | 4h |
| 6.3 | Implement PubMed client | `core/ingestion/pubmed.py` using Entrez E-utilities. Search, fetch abstracts, extract MeSH terms as domains. | 4h |
| 6.4 | Implement PDF parser | `core/ingestion/pdf_parser.py` using PyMuPDF. Extract title, abstract, authors, references from PDF. Fallback to LLM extraction if structure unclear. | 5h |
| 6.5 | Implement BibTeX importer | `core/ingestion/bibtex_importer.py` using `bibtexparser`. Parse `.bib` files, create Paper objects, handle encoding issues. | 3h |
| 6.6 | Implement URL scraper for papers | `core/ingestion/url_scraper.py`. Detect if URL is arXiv, Semantic Scholar, PubMed, or generic. Extract metadata accordingly. | 3h |
| 6.7 | Add `/api/ingest/*` endpoints | `POST /api/ingest/arxiv`, `POST /api/ingest/semantic-scholar`, `POST /api/ingest/pubmed`, `POST /api/ingest/pdf` (multipart), `POST /api/ingest/bibtex` (multipart), `POST /api/ingest/url`, `POST /api/ingest/manual`. | 4h |
| 6.8 | Build IngestionPanel (frontend) | `components/ingestion/IngestionPanel.tsx` with tabs: Search (Semantic Scholar/PubMed), Upload PDF, Import BibTeX, Add URL, Manual Entry. | 6h |
| 6.9 | Add ingestion progress tracking | Background task tracking with status endpoint `GET /api/ingest/status/{job_id}`. WebSocket updates for real-time progress. | 4h |
| 6.10 | Auto-embed on ingestion | All ingestion paths automatically generate vector embeddings and add to ChromaDB. | 2h |
| 6.11 | Auto-compile wiki on ingestion | New papers automatically trigger wiki compilation (async, queued). | 2h |
| 6.12 | Add source filtering in search | Search results show source badge (arXiv, Semantic Scholar, PubMed, PDF, Manual). Filter by source. | 2h |

**Deliverables:**
- 6 ingestion sources: arXiv, Semantic Scholar, PubMed, PDF, BibTeX, URL, Manual
- Unified paper model across all sources
- Ingestion panel with all source types
- Automatic embedding and wiki compilation on ingestion
- Source filtering in search results

**Verification Criteria:**
- [ ] Semantic Scholar search returns papers with correct metadata
- [ ] PubMed search returns papers with MeSH terms as domains
- [ ] PDF upload extracts title, abstract, authors correctly
- [ ] BibTeX import handles encoding and special characters
- [ ] URL scraping detects source type and extracts appropriate metadata
- [ ] Manual entry form creates paper with all required fields
- [ ] All ingested papers appear in search within 5 seconds
- [ ] Ingestion progress shown in real-time via WebSocket

---

### Phase 7: Tool Integration & Polish (Weeks 15-16)

**Goal:** Add code execution sandbox, visualization tools, collaboration features, and final polish.

**Complexity:** M

**Dependencies:** All previous phases

#### Tasks

| # | Task | Details | Est. |
|---|------|---------|------|
| 7.1 | Implement code execution sandbox | `core/tools/code_executor.py` using `subprocess` with Docker or `restrictedpython`. Execute Python code, return stdout/stderr. Timeout 30s. | 5h |
| 7.2 | Add `/api/tools/execute` endpoint | POST endpoint accepting `{code, language}`. Returns `{stdout, stderr, exit_code, execution_time}`. | 2h |
| 7.3 | Build CodeExecutor component | `components/tools/CodeExecutor.tsx` with Monaco editor, run button, output panel. | 4h |
| 7.4 | Implement data visualization tool | `core/tools/visualizer.py` generating matplotlib/seaborn charts. Return as base64 PNG. | 3h |
| 7.5 | Add citation graph visualization | `components/graph/CitationGraphPanel.tsx` showing citation relationships between papers. | 4h |
| 7.6 | Implement shared session export | `POST /api/sessions/{id}/share` generating shareable link with read-only access. | 3h |
| 7.7 | Add team annotations | `POST /api/papers/{id}/annotations` with `{user, text, position, created_at}`. Store in SQLite. | 3h |
| 7.8 | Build AnnotationPanel (frontend) | `components/papers/AnnotationPanel.tsx` showing annotations on paper detail view. Add/edit/delete. | 4h |
| 7.9 | Add command palette | `components/ui/CommandPalette.tsx` with fuzzy search for: navigate to session, run agent, search papers, create plan. Trigger with Ctrl+K. | 4h |
| 7.10 | Implement conversation branching | `POST /api/sessions/{id}/branch` creating a new session from a specific message. Enable "try different direction" UX. | 3h |
| 7.11 | Add message pinning | `PATCH /api/messages/{id}/pin` to pin important messages. Show pinned messages in sidebar. | 2h |
| 7.12 | Add export conversation | `GET /api/sessions/{id}/export?format=markdown|pdf|json`. Multi-format export. | 2h |
| 7.13 | Performance optimization | Add response caching for search, implement connection pooling, optimize ChromaDB queries. | 4h |
| 7.14 | Comprehensive testing | Unit tests for all services, integration tests for API endpoints, E2E tests for critical user flows. | 8h |
| 2.15 | Documentation | Update README, add API documentation, create user guide, add architecture diagrams. | 4h |

**Deliverables:**
- Code execution sandbox with Python support
- Data visualization tool
- Citation graph visualization
- Shared session export
- Team annotations on papers
- Command palette (Ctrl+K)
- Conversation branching
- Message pinning
- Multi-format conversation export
- Comprehensive test suite
- Updated documentation

**Verification Criteria:**
- [ ] Code execution sandbox runs Python code safely with timeout
- [ ] Visualization tool generates charts from data
- [ ] Citation graph renders correctly with paper nodes
- [ ] Shared session link provides read-only access
- [ ] Annotations persist and display on paper detail
- [ ] Command palette navigates to all major features
- [ ] Conversation branching creates new session from message
- [ ] Pinned messages appear in sidebar
- [ ] Export produces valid Markdown, PDF, and JSON
- [ ] All tests pass (unit + integration + E2E)
- [ ] Documentation covers all features

---

## 4. Database Schema Changes

### 4.1 New Tables (SQLite via SQLAlchemy + Alembic)

```sql
-- Research Plans
CREATE TABLE research_plans (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'draft',  -- draft, active, completed, archived
    template TEXT,                 -- literature_review, methodology_comparison, etc.
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Hypotheses
CREATE TABLE hypotheses (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES research_plans(id) ON DELETE CASCADE,
    statement TEXT NOT NULL,
    status TEXT DEFAULT 'proposed',  -- proposed, testing, supported, refuted
    evidence TEXT,                   -- JSON array of supporting paper IDs
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Milestones
CREATE TABLE milestones (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES research_plans(id) ON DELETE CASCADE,
    title TEXT NOT NULL,
    description TEXT,
    due_date TIMESTAMP,
    status TEXT DEFAULT 'pending',  -- pending, in_progress, completed, blocked
    order_index INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tasks
CREATE TABLE tasks (
    id TEXT PRIMARY KEY,
    plan_id TEXT NOT NULL REFERENCES research_plans(id) ON DELETE CASCADE,
    milestone_id TEXT REFERENCES milestones(id) ON DELETE SET NULL,
    title TEXT NOT NULL,
    description TEXT,
    status TEXT DEFAULT 'pending',  -- pending, in_progress, completed, failed
    assigned_agent TEXT,            -- agent name
    result TEXT,                    -- JSON result from agent
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Agent Results Cache
CREATE TABLE agent_results (
    id TEXT PRIMARY KEY,
    agent_name TEXT NOT NULL,
    query_hash TEXT NOT NULL,       -- SHA256 of query + context
    query TEXT NOT NULL,
    result TEXT NOT NULL,           -- JSON result
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,
    UNIQUE(agent_name, query_hash)
);

-- Annotations
CREATE TABLE annotations (
    id TEXT PRIMARY KEY,
    paper_id TEXT NOT NULL,         -- arxiv_id or source_id
    user TEXT NOT NULL,
    text TEXT NOT NULL,
    position TEXT,                  -- JSON: {section, offset, length}
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Ingestion Jobs
CREATE TABLE ingestion_jobs (
    id TEXT PRIMARY KEY,
    source TEXT NOT NULL,           -- arxiv, semantic_scholar, pubmed, pdf, bibtex, url, manual
    status TEXT DEFAULT 'pending',  -- pending, running, completed, failed
    progress REAL DEFAULT 0,        -- 0.0 to 1.0
    total_items INTEGER DEFAULT 0,
    processed_items INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_at TIMESTAMP
);

-- Shared Sessions
CREATE TABLE shared_sessions (
    id TEXT PRIMARY KEY,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id),
    access_token TEXT UNIQUE NOT NULL,
    expires_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pinned Messages
CREATE TABLE pinned_messages (
    id TEXT PRIMARY KEY,
    message_id INTEGER NOT NULL REFERENCES chat_messages(id) ON DELETE CASCADE,
    session_id TEXT NOT NULL REFERENCES chat_sessions(id) ON DELETE CASCADE,
    pinned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_id)
);

-- Papers (unified model for all sources)
CREATE TABLE papers (
    id TEXT PRIMARY KEY,            -- UUID
    source TEXT NOT NULL,           -- arxiv, semantic_scholar, pubmed, pdf, bibtex, url, manual
    source_id TEXT NOT NULL,        -- arxiv_id, S2 ID, PubMed ID, etc.
    title TEXT NOT NULL,
    abstract TEXT,
    authors TEXT,                   -- JSON array
    url TEXT,
    pdf_path TEXT,
    domains TEXT,                   -- JSON array
    categories TEXT,                -- JSON array
    published_date TEXT,
    ingested_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    embedding_id TEXT,              -- ChromaDB document ID
    wiki_compiled BOOLEAN DEFAULT FALSE,
    UNIQUE(source, source_id)
);

-- Paper citations (for citation graph)
CREATE TABLE paper_citations (
    id TEXT PRIMARY KEY,
    citing_paper_id TEXT NOT NULL REFERENCES papers(id),
    cited_paper_id TEXT NOT NULL REFERENCES papers(id),
    UNIQUE(citing_paper_id, cited_paper_id)
);
```

### 4.2 Existing Tables (Modified)

```sql
-- chat_sessions: add columns
ALTER TABLE chat_sessions ADD COLUMN plan_id TEXT REFERENCES research_plans(id);
ALTER TABLE chat_sessions ADD COLUMN is_shared BOOLEAN DEFAULT FALSE;

-- chat_messages: add columns
ALTER TABLE chat_messages ADD COLUMN pinned BOOLEAN DEFAULT FALSE;
ALTER TABLE chat_messages ADD COLUMN branch_parent_id INTEGER REFERENCES chat_messages(id);

-- papers (existing FTS5 table): keep as-is, add new unified papers table
-- The existing FTS5 papers table continues to serve keyword search
-- New unified papers table serves all sources
```

### 4.3 Migration Strategy

1. Create `alembic/versions/001_initial_schema.py` for all new tables
2. Run `alembic upgrade head` to apply migrations
3. Backfill script `scripts/migrate_to_unified_papers.py` copies existing wiki entries to unified `papers` table
4. Verify data integrity: count matches between old and new tables

---

## 5. API Endpoint Design

### 5.1 Backend Router Structure

```
server/
├── app.py                    # FastAPI app, CORS, middleware, lifespan
├── routers/
│   ├── chat.py               # /api/chat, /api/chat/stream
│   ├── sessions.py           # /api/sessions/*
│   ├── search.py             # /api/search/*
│   ├── papers.py             # /api/papers/*, /api/domains/*
│   ├── wiki.py               # /api/wiki/*
│   ├── settings.py           # /api/settings/*
│   ├── web.py                # /api/web/*
│   ├── agents.py             # /api/agents/*
│   ├── plans.py              # /api/plans/*, /api/tasks/*
│   ├── graph.py              # /api/graph/*
│   ├── discover.py           # /api/discover/*
│   ├── ingest.py             # /api/ingest/*
│   ├── compare.py            # /api/compare/*
│   ├── tools.py              # /api/tools/*
│   └── export.py             # /api/export/*
├── services/
│   ├── chat_service.py
│   ├── search_service.py
│   ├── plan_service.py
│   ├── ingestion_service.py
│   └── agent_service.py
└── websocket/
    └── agents.py             # /ws/agents
```

### 5.2 Complete Endpoint Inventory

#### Chat (existing, enhanced)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| POST | `/api/chat` | `ChatRequest` | `ChatResponse` | Existing, unchanged |
| POST | `/api/chat/stream` | `ChatRequest` | SSE stream | Existing, add agent mode |
| POST | `/api/chat/stream` | `ChatRequest{mode: "research"}` | SSE stream | New: routes through swarm |

#### Sessions (existing, enhanced)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| GET | `/api/sessions` | `?limit=50&offset=0` | `{sessions[]}` | Existing |
| POST | `/api/sessions` | `{title}` | `{id, title}` | Existing |
| GET | `/api/sessions/{id}` | — | `{session, messages[]}` | Existing |
| PATCH | `/api/sessions/{id}` | `{title}` | `{id, title}` | Existing |
| DELETE | `/api/sessions/{id}` | — | `{deleted}` | Existing |
| GET | `/api/sessions/{id}/export` | `?format=json` | JSON file | Existing |
| POST | `/api/sessions/{id}/branch` | `{message_id}` | `{new_session_id}` | **New** |
| POST | `/api/sessions/{id}/share` | `{expires_in_hours}` | `{share_url, token}` | **New** |
| GET | `/api/sessions/{id}/pinned` | — | `{messages[]}` | **New** |

#### Search (new + enhanced)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| GET | `/api/search` | `?q=&limit=20` | `{results[]}` | Existing (BM25) |
| POST | `/api/search/hybrid` | `{query, limit, mode}` | `{results[], scores}` | **New** |
| GET | `/api/search/stats` | — | `{query_dist, mode_usage}` | **New** |

#### Papers (enhanced)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| GET | `/api/papers` | `?limit=50&source=arxiv` | `{papers[]}` | Enhanced with source filter |
| GET | `/api/papers/{id}` | — | `{paper}` | Enhanced with annotations |
| GET | `/api/domains` | — | `{domains[]}` | Existing |
| GET | `/api/domains/{name}/papers` | — | `{papers[]}` | Existing |
| POST | `/api/papers/{id}/annotations` | `{user, text, position}` | `{annotation}` | **New** |
| GET | `/api/papers/{id}/annotations` | — | `{annotations[]}` | **New** |
| DELETE | `/api/papers/{id}/annotations/{aid}` | — | `{deleted}` | **New** |

#### Agents (new)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| GET | `/api/agents` | — | `{agents[]}` | List available agents |
| POST | `/api/agents/{name}/run` | `{query, context}` | `{result}` | Run single agent |
| POST | `/api/agents/swarm` | `{query, agents[]}` | `{combined_result}` | Run swarm |
| GET | `/api/agents/config` | — | `{config}` | Agent configuration |
| PUT | `/api/agents/config` | `{config}` | `{config}` | Update config |

#### Plans (new)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| GET | `/api/plans` | `?status=active` | `{plans[]}` | List plans |
| POST | `/api/plans` | `{title, template}` | `{plan}` | Create plan |
| GET | `/api/plans/{id}` | — | `{plan, hypotheses[], milestones[]}` | Plan detail |
| PATCH | `/api/plans/{id}` | `{title, status}` | `{plan}` | Update plan |
| DELETE | `/api/plans/{id}` | — | `{deleted}` | Delete plan |
| POST | `/api/plans/{id}/hypotheses` | `{statement}` | `{hypothesis}` | Add hypothesis |
| POST | `/api/plans/{id}/milestones` | `{title, due_date}` | `{milestone}` | Add milestone |
| POST | `/api/plans/{id}/export` | `{format}` | File download | Export report |
| POST | `/api/plans/{id}/literature-review` | — | `{review}` | Generate lit review |

#### Tasks (new)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| GET | `/api/plans/{plan_id}/tasks` | `?status=pending` | `{tasks[]}` | List tasks |
| POST | `/api/plans/{plan_id}/tasks` | `{title, milestone_id}` | `{task}` | Create task |
| PATCH | `/api/tasks/{id}` | `{status, result}` | `{task}` | Update task |
| DELETE | `/api/tasks/{id}` | — | `{deleted}` | Delete task |

#### Knowledge Graph (new)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| GET | `/api/graph/nodes` | `?type=paper` | `{nodes[]}` | Graph nodes |
| GET | `/api/graph/edges` | `?type=cross_domain` | `{edges[]}` | Graph edges |
| POST | `/api/graph/path` | `{from, to}` | `{path[]}` | Find path |
| GET | `/api/graph/bridges/{a}/{b}` | — | `{papers[]}` | Domain bridges |
| POST | `/api/graph/rebuild` | — | `{status}` | Rebuild graph |

#### Discovery (new)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| POST | `/api/discover/connections` | `{paper_id, limit}` | `{connections[]}` | Cross-domain links |
| POST | `/api/discover/analogies` | `{source_domain, target_domain}` | `{analogies[]}` | Analogy generation |
| POST | `/api/discover/trends` | `{domains[], timeframe}` | `{trends[]}` | Trend analysis |

#### Ingestion (new)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| POST | `/api/ingest/arxiv` | `{query, max_results}` | `{job_id}` | arXiv ingestion |
| POST | `/api/ingest/semantic-scholar` | `{query, limit}` | `{job_id}` | S2 ingestion |
| POST | `/api/ingest/pubmed` | `{query, limit}` | `{job_id}` | PubMed ingestion |
| POST | `/api/ingest/pdf` | multipart form | `{job_id}` | PDF upload |
| POST | `/api/ingest/bibtex` | multipart form | `{job_id}` | BibTeX import |
| POST | `/api/ingest/url` | `{url}` | `{job_id}` | URL scraping |
| POST | `/api/ingest/manual` | `{title, abstract, ...}` | `{paper}` | Manual entry |
| GET | `/api/ingest/status/{job_id}` | — | `{status, progress}` | Job status |

#### Comparison (new)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| POST | `/api/compare/papers` | `{paper_ids[], dimensions[]}` | `{comparison}` | Paper comparison |

#### Tools (new)
| Method | Endpoint | Request | Response | Notes |
|--------|----------|---------|----------|-------|
| POST | `/api/tools/execute` | `{code, language}` | `{stdout, stderr}` | Code execution |
| POST | `/api/tools/visualize` | `{data, chart_type}` | `{image_base64}` | Data visualization |

#### WebSocket
| Endpoint | Events | Notes |
|----------|--------|-------|
| `/ws/agents` | `{agent, status, progress, result}` | Real-time agent progress |
| `/ws/ingestion` | `{job_id, status, progress}` | Real-time ingestion progress |

---

## 6. Frontend Component Tree

### 6.1 Directory Structure

```
frontend/
├── src/
│   ├── main.tsx                    # Entry point
│   ├── App.tsx                     # Root component with routing
│   ├── stores/
│   │   ├── chatStore.ts            # Sessions, messages, current session
│   │   ├── agentStore.ts           # Agent state, results, progress
│   │   ├── planStore.ts            # Research plans, tasks, hypotheses
│   │   ├── paperStore.ts           # Papers, domains, ingestion
│   │   ├── graphStore.ts           # Knowledge graph nodes/edges
│   │   └── themeStore.ts           # Dark/light theme
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx       # Main layout: sidebar + main content
│   │   │   ├── Sidebar.tsx         # Collapsible sidebar with tabs
│   │   │   └── Header.tsx          # Top bar with mode toggle, model selector
│   │   ├── chat/
│   │   │   ├── ChatPanel.tsx       # Main chat area
│   │   │   ├── MessageList.tsx     # Scrollable message list
│   │   │   ├── MessageBubble.tsx   # Individual message (user/assistant)
│   │   │   ├── ChatInput.tsx       # Input area with paper chips
│   │   │   ├── MarkdownRenderer.tsx # react-markdown wrapper
│   │   │   ├── ThinkingTrace.tsx   # Collapsible reasoning trace
│   │   │   ├── SourceChips.tsx     # Source paper chips
│   │   │   └── WebSearchPanel.tsx  # Collapsible web search
│   │   ├── sidebar/
│   │   │   ├── SessionList.tsx     # Chat history list
│   │   │   ├── MemoryPanel.tsx     # Wiki stats, entities, notes
│   │   │   ├── SourcesBrowser.tsx  # Domain/paper hierarchy
│   │   │   └── SettingsPanel.tsx   # Configuration forms
│   │   ├── papers/
│   │   │   ├── PaperDetailModal.tsx # Paper detail dialog
│   │   │   ├── PaperCard.tsx       # Paper preview card
│   │   │   └── AnnotationPanel.tsx # Paper annotations
│   │   ├── agents/
│   │   │   ├── AgentPanel.tsx      # Agent list and controls
│   │   │   ├── AgentCard.tsx       # Individual agent card
│   │   │   ├── AgentProgress.tsx   # Live progress indicator
│   │   │   └── AgentResult.tsx     # Formatted agent output
│   │   ├── plans/
│   │   │   ├── PlanPanel.tsx       # Plan list and detail
│   │   │   ├── PlanEditor.tsx      # Create/edit plan form
│   │   │   ├── HypothesisList.tsx  # Hypothesis editor
│   │   │   ├── MilestoneTimeline.tsx # Milestone timeline
│   │   │   ├── TaskBoard.tsx       # Kanban task board
│   │   │   └── ExportPanel.tsx     # Report export
│   │   ├── graph/
│   │   │   ├── KnowledgeGraphPanel.tsx # Force graph visualization
│   │   │   ├── CitationGraphPanel.tsx  # Citation relationships
│   │   │   └── GraphTooltip.tsx    # Node hover detail
│   │   ├── compare/
│   │   │   ├── PaperComparison.tsx # Comparison matrix
│   │   │   └── ComparisonTable.tsx # Sortable comparison table
│   │   ├── ingestion/
│   │   │   ├── IngestionPanel.tsx  # Multi-source ingestion UI
│   │   │   ├── PdfUploader.tsx     # PDF drag-drop upload
│   │   │   ├── BibTeXImporter.tsx  # BibTeX file import
│   │   │   ├── UrlScraper.tsx      # URL input and scrape
│   │   │   ├── ManualEntryForm.tsx # Manual paper entry
│   │   │   └── IngestionProgress.tsx # Job progress tracker
│   │   ├── tools/
│   │   │   ├── CodeExecutor.tsx    # Monaco editor + output
│   │   │   └── Visualizer.tsx      # Chart display
│   │   └── ui/
│   │       ├── CommandPalette.tsx  # Ctrl+K command palette
│   │       ├── ThemeToggle.tsx     # Dark/light switch
│   │       ├── LoadingSkeleton.tsx # Loading placeholder
│   │       └── ErrorBoundary.tsx   # React error boundary
│   ├── hooks/
│   │   ├── useChatStream.ts        # SSE streaming hook
│   │   ├── useWebSocket.ts         # WebSocket connection hook
│   │   ├── useDragDrop.ts          # Paper drag-drop hook
│   │   └── useKeyboardShortcuts.ts # Keyboard shortcut hook
│   ├── lib/
│   │   ├── api.ts                  # API client (fetch wrapper)
│   │   ├── websocket.ts            # WebSocket client
│   │   ├── markdown.ts             # Markdown rendering config
│   │   └── utils.ts                # Utility functions
│   └── types/
│       ├── chat.ts                 # Chat-related types
│       ├── paper.ts                # Paper-related types
│       ├── agent.ts                # Agent-related types
│       ├── plan.ts                 # Plan-related types
│       └── graph.ts                # Graph-related types
├── index.html
├── vite.config.ts
├── tailwind.config.ts
└── tsconfig.json
```

### 6.2 Component Hierarchy

```
App
├── AppLayout
│   ├── Sidebar
│   │   ├── SidebarHeader (logo, new chat button)
│   │   ├── TabNavigation (history, memory, sources, agents, plans, settings)
│   │   ├── TabContent
│   │   │   ├── SessionList → SessionItem × N
│   │   │   ├── MemoryPanel → MemoryStats, EntityList, NoteList
│   │   │   ├── SourcesBrowser → DateGroup → CategoryGroup → PaperItem × N
│   │   │   ├── AgentPanel → AgentCard × N, AgentProgress, AgentResult
│   │   │   ├── PlanPanel → PlanList, PlanDetail, HypothesisList, MilestoneTimeline, TaskBoard
│   │   │   └── SettingsPanel → SettingsSection × N
│   │   └── SidebarFooter (model badge, version)
│   ├── Header
│   │   ├── MenuButton (mobile)
│   │   ├── Title + Subtitle
│   │   ├── ResearchModeToggle
│   │   ├── ModelSelector
│   │   └── WebSearchButton
│   └── MainContent
│       ├── WebSearchPanel (conditional)
│       ├── ChatPanel
│       │   ├── MessageList
│       │   │   ├── WelcomeMessage
│       │   │   ├── MessageBubble (user) × N
│       │   │   ├── MessageBubble (assistant) × N
│       │   │   │   ├── MessageLabel
│       │   │   │   ├── ThinkingTrace
│       │   │   │   ├── MarkdownRenderer
│       │   │   │   └── SourceChips
│       │   │   └── LoadingIndicator
│       │   └── ChatInput
│       │       ├── DroppedPaperChips
│       │       ├── TextArea
│       │       └── SendButton
│       ├── KnowledgeGraphPanel (tab view)
│       │   ├── ForceGraph2D
│       │   └── GraphTooltip
│       ├── PlanPanel (tab view)
│       │   ├── PlanEditor
│       │   ├── HypothesisList
│       │   ├── MilestoneTimeline
│       │   └── TaskBoard
│       └── IngestionPanel (tab view)
│           ├── SearchTab (Semantic Scholar / PubMed)
│           ├── PdfUploader
│           ├── BibTeXImporter
│           ├── UrlScraper
│           └── ManualEntryForm
├── PaperDetailModal (overlay)
├── CommandPalette (overlay)
└── ErrorBoundary
```

### 6.3 Key Component Specifications

#### ChatPanel
- **Props:** `sessionId`, `messages`, `onSend`, `onStreamUpdate`
- **State:** `isStreaming`, `fullContent`, `fullThinking`, `sources`
- **Behavior:** SSE streaming with `useChatStream` hook. Accumulates content chunks. Renders thinking trace separately from answer.

#### KnowledgeGraphPanel
- **Props:** `nodes`, `edges`, `onNodeClick`
- **State:** `selectedNode`, `filterDomain`, `zoom`, `layout`
- **Behavior:** Force-directed graph with domain-colored nodes. Click node → show paper detail in sidebar. Filter by domain. Zoom/pan controls.

#### AgentPanel
- **Props:** `agents`, `onRunAgent`, `onRunSwarm`
- **State:** `runningAgents`, `results`, `progress`
- **Behavior:** WebSocket connection for real-time progress. Shows agent cards with run button. Displays combined results after swarm completes.

#### TaskBoard
- **Props:** `tasks`, `onUpdateStatus`, `onAssignAgent`
- **State:** `columns` (pending, in_progress, completed)
- **Behavior:** Kanban columns. Drag tasks between columns to change status. Click task to edit details. Assign agent from dropdown.

---

## 7. Agent Architecture

### 7.1 Agent Communication Model

```
                    ┌─────────────────────┐
                    │  SwarmCoordinator   │
                    │                     │
                    │  - Decompose query  │
                    │  - Dispatch tasks   │
                    │  - Combine results  │
                    │  - Resolve conflicts│
                    └──────┬──┬──┬──┬─────┘
                           │  │  │  │
              ┌────────────┘  │  │  └────────────┐
              │               │  │               │
    ┌─────────▼─────┐ ┌──────▼──▼──────┐ ┌──────▼──────────┐
    │ Literature    │ │ Methodology    │ │ Cross-Domain    │
    │ Reviewer      │ │ Analyst        │ │ Connector       │
    └───────┬───────┘ └───────┬────────┘ └────────┬────────┘
            │                 │                    │
            └─────────────────┼────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
    ┌─────────▼─────┐ ┌──────▼──────┐ ┌──────▼──────────┐
    │ Fact Checker  │ │ Research    │ │ (Results to     │
    │               │ │ Planner     │ │  Coordinator)   │
    └───────────────┘ └─────────────┘ └─────────────────┘
```

### 7.2 Agent Base Class

```python
# core/agents/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime

@dataclass
class AgentResult:
    agent_name: str
    query: str
    result: dict[str, Any]
    sources: list[dict] = field(default_factory=list)
    confidence: float = 0.0
    execution_time_ms: int = 0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

class BaseAgent(ABC):
    name: str
    description: str
    system_prompt: str
    max_papers: int = 10
    timeout_seconds: int = 120

    @abstractmethod
    async def run(self, query: str, context: dict) -> AgentResult:
        """Execute the agent's research task."""
        pass

    async def _search_papers(self, query: str, limit: int = None) -> list[dict]:
        """Search papers using hybrid search."""
        from core.search_engine import hybrid_search
        return hybrid_search(query, limit=limit or self.max_papers)

    async def _call_llm(self, messages: list[dict]) -> str:
        """Call the LLM with messages."""
        from core.model_client import ModelClient
        client = ModelClient()
        return client.generate(messages=messages)
```

### 7.3 Agent Specifications

#### LiteratureReviewerAgent
- **Purpose:** Comprehensive literature survey for a research topic
- **Input:** Research query, optional domain filter
- **Process:**
  1. Hybrid search for relevant papers (top 15)
  2. Group papers by contribution type
  3. Synthesize summary per group
  4. Identify research gaps
- **Output:** `{summary, paper_groups[], gaps[], key_findings[]}`
- **System Prompt:** "You are a literature review specialist. Given a research topic and a set of papers, produce a structured literature review..."

#### MethodologyAnalystAgent
- **Purpose:** Analyze and compare research methodologies
- **Input:** Research query, paper IDs
- **Process:**
  1. Extract methods from each paper
  2. Compare strengths/weaknesses
  3. Identify methodological trends
- **Output:** `{methods[], comparison_table[], trends[], recommendations[]}`
- **System Prompt:** "You are a methodology analyst. Compare the research methods used in the provided papers..."

#### CrossDomainConnectorAgent
- **Purpose:** Find non-obvious connections between fields
- **Input:** Source domain, target domain (or paper ID)
- **Process:**
  1. Query knowledge graph for domain bridge papers
  2. Compute semantic similarity across domains
  3. Generate bridge explanations
- **Output:** `{connections[], bridge_papers[], explanations[], confidence_scores[]}`
- **System Prompt:** "You are a cross-domain connector. Find structural parallels between mechanisms in different scientific fields..."

#### FactCheckerAgent
- **Purpose:** Verify claims against source papers
- **Input:** Claims to verify, source paper IDs
- **Process:**
  1. For each claim, find supporting/contradicting evidence
  2. Score confidence based on evidence quality
  3. Flag unsupported claims
- **Output:** `{claims: [{claim, verified, evidence, confidence, source_ids}]}`
- **System Prompt:** "You are a fact checker. Given claims and source papers, verify each claim against the actual paper content..."

#### ResearchPlannerAgent
- **Purpose:** Create structured research plans
- **Input:** Research topic, available papers
- **Process:**
  1. Identify key research questions
  2. Propose hypotheses
  3. Suggest milestones and experiments
- **Output:** `{research_questions[], hypotheses[], milestones[], suggested_experiments[]}`
- **System Prompt:** "You are a research planner. Given a research topic, create a structured research plan with hypotheses, milestones..."

### 7.4 Swarm Coordinator

```python
# core/agents/swarm_coordinator.py
class SwarmCoordinator:
    def __init__(self, agent_registry: AgentRegistry):
        self.registry = agent_registry
        self.decomposition_prompt = DECOMPOSITION_PROMPT

    async def execute(self, query: str, agent_names: list[str] = None) -> dict:
        # 1. Decompose query into sub-tasks
        sub_tasks = await self._decompose(query)

        # 2. Select agents for each sub-task
        assignments = self._assign_agents(sub_tasks, agent_names)

        # 3. Execute agents (parallel where possible)
        results = await self._execute_parallel(assignments)

        # 4. Combine results with consensus
        combined = await self._combine(results, query)

        return combined

    async def _decompose(self, query: str) -> list[dict]:
        """Use LLM to decompose query into sub-tasks."""
        # Returns: [{task, suggested_agent, dependencies[]}]

    async def _execute_parallel(self, assignments: list[dict]) -> list[AgentResult]:
        """Execute independent agents in parallel using asyncio.gather."""
        # Group by dependency level, execute each level in parallel

    async def _combine(self, results: list[AgentResult], query: str) -> dict:
        """Use LLM to combine agent results into coherent response."""
        # Handles conflicts via consensus voting
```

### 7.5 Consensus Mechanism

When agents produce conflicting results:
1. **Majority vote:** If 3+ agents agree, use majority result
2. **Confidence weighting:** Weight each agent's output by its confidence score
3. **LLM arbitration:** If still conflicted, use LLM to resolve with evidence from both sides
4. **Flag uncertainty:** Present both perspectives to user with confidence scores

---

## 8. Migration Strategy

### 8.1 Data Migration

#### Phase 1: No data changes
- Frontend migration does not touch backend data
- All existing SQLite tables remain unchanged
- Wiki markdown files remain in place

#### Phase 2: Vector backfill
```bash
# Backfill script
python scripts/embed_papers.py
# Reads all wiki entries → generates embeddings → upserts to ChromaDB
# Does NOT modify existing data
```

#### Phase 3: Graph build
```bash
# Graph build script
python scripts/rebuild_graph.py
# Reads all wiki files → builds NetworkX graph → serializes to data/graph.json
# Does NOT modify existing data
```

#### Phase 5: Schema migration
```bash
# Alembic migration
alembic upgrade head
# Creates new tables: research_plans, hypotheses, milestones, tasks, etc.
# Does NOT modify existing chat_sessions or chat_messages tables
```

#### Phase 6: Unified paper model
```bash
# Migration script
python scripts/migrate_to_unified_papers.py
# Copies existing wiki entries to new unified papers table
# Preserves existing FTS5 papers table for backward compatibility
```

### 8.2 Frontend Migration Strategy

1. **Side-by-side development:** New React app runs on `localhost:5173`, proxies API to `localhost:8000`
2. **Feature parity first:** Implement all existing features before adding new ones
3. **Gradual cutover:** Once React app has feature parity, switch production to serve Vite build
4. **Fallback:** Keep `server/templates/index.html` as fallback during transition

### 8.3 Backward Compatibility

| Component | v2.0 Compatibility | Notes |
|-----------|-------------------|-------|
| SQLite tables | Full | Existing tables unchanged, new tables added |
| Wiki files | Full | Markdown files remain in `data/wiki/` |
| API endpoints | Full | All existing endpoints preserved |
| Config format | Full | `user_config.json` format unchanged |
| Paper storage | Full | Domain-based JSON files remain |
| FTS5 index | Full | Continues to serve keyword search |

### 8.4 Rollback Plan

1. **Database:** Alembic supports `alembic downgrade -1` for each migration
2. **Frontend:** Keep old `server/templates/index.html` — revert by changing FastAPI mount
3. **ChromaDB:** Delete `data/chroma/` directory and re-run backfill
4. **Graph:** Delete `data/graph.json` and re-run rebuild
5. **Agents:** New code is additive — remove `core/agents/` directory to disable

---

## 9. Risk Assessment

### 9.1 Technical Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ChromaDB memory usage grows unbounded | Medium | High | Implement TTL-based cleanup, limit collection size, monitor memory |
| LLM API rate limits during agent swarm | High | Medium | Implement retry with exponential backoff, queue requests, cache results |
| Vector embedding quality insufficient for cross-domain | Medium | High | Test with known cross-domain queries, fallback to BM25, consider larger model |
| Knowledge graph becomes too large to serialize | Low | Medium | Use incremental updates, store edges in SQLite instead of JSON |
| React bundle size exceeds budget | Medium | Low | Code splitting, lazy loading, tree shaking, monitor with `vite-bundle-visualizer` |
| WebSocket connections drop during long agent runs | Medium | Medium | Implement reconnection logic, heartbeat, persist progress in SQLite |
| PDF parsing fails on complex layouts | High | Low | Fallback to LLM-based extraction, log failures for manual review |
| SQLite concurrent write conflicts | Low | Medium | Use WAL mode (already enabled), implement write queue for high-write operations |

### 9.2 Project Risks

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| Scope creep — too many features per phase | High | High | Strict phase boundaries, defer non-critical features to later phases |
| Phase 1 takes longer than estimated (React migration) | Medium | High | Prioritize core chat functionality first, defer settings/memory panels |
| Agent prompts produce inconsistent results | High | Medium | Iterative prompt engineering, add evaluation harness, use structured output |
| Team unfamiliar with React/TypeScript | Medium | Medium | Provide component templates, pair programming, code review |
| External API changes (Semantic Scholar, PubMed) | Low | Medium | Abstract API clients behind interfaces, add integration tests, monitor |
| Performance degradation with 1000+ papers | Medium | High | Benchmark at each phase, add pagination, optimize ChromaDB queries |

### 9.3 Mitigation Priority Matrix

```
High Impact
    │
    │  ● ChromaDB memory     ● Scope creep
    │  ● Embedding quality   ● Phase 1 timeline
    │
    │  ● LLM rate limits     ● Agent consistency
    │  ● WebSocket drops     ● Team familiarity
    │
    │                        ● SQLite conflicts
    │  ● Graph size          ● API changes
    │  ● Bundle size         ● Performance at scale
    │
    └──────────────────────────────────────
      Low Probability              High Probability
```

---

## 10. Quick Wins

These can be implemented **immediately** on the current stack (no React migration needed):

### 10.1 Backend Quick Wins (1-2 days each)

| # | Task | Impact | Effort |
|---|------|--------|--------|
| Q1 | **Split `app.py` into routers** | Improves maintainability, enables parallel development | 4h |
| Q2 | **Add response caching** for search results | Reduces LLM calls, faster response times | 2h |
| Q3 | **Add request rate limiting** | Prevents abuse, protects LLM API quotas | 2h |
| Q4 | **Improve `formatMarkdown()` in app.js** | Better code blocks, tables, lists in chat | 3h |
| Q5 | **Add paper count to domain display** | Better UX in sources browser | 1h |
| Q6 | **Add search result highlighting** | Shows why each paper matched | 3h |
| Q7 | **Add conversation export to Markdown** | Users can save conversations | 2h |
| Q8 | **Add auto-title generation** | Use LLM to generate session titles from first message | 2h |
| Q9 | **Add error toast notifications** | Better error feedback in UI | 2h |
| Q10 | **Add loading states for all async operations** | Better UX during data fetches | 3h |

### 10.2 Frontend Quick Wins (1-2 days each)

| # | Task | Impact | Effort |
|---|------|--------|--------|
| Q11 | **Add code block syntax highlighting** | Use `highlight.js` in `formatMarkdown()` | 2h |
| Q12 | **Add copy-to-clipboard for messages** | UX improvement | 1h |
| Q13 | **Add scroll-to-bottom button** | UX improvement for long conversations | 1h |
| Q14 | **Add paper count badge on domains** | Visual improvement | 1h |
| Q15 | **Add keyboard shortcut for new chat (Ctrl+N)** | Power user feature | 1h |
| Q16 | **Add "scroll to latest" indicator** | Shows when new messages arrive while scrolled up | 2h |
| Q17 | **Improve mobile sidebar** | Make sidebar a slide-out drawer on mobile | 3h |
| Q18 | **Add session search** | Filter sessions by title in sidebar | 2h |

### 10.3 Quick Win Implementation Order

```
Week 1: Q1 (split app.py), Q4 (better markdown), Q11 (syntax highlighting)
Week 1: Q7 (export), Q8 (auto-title), Q12 (copy), Q13 (scroll button)
Week 2: Q2 (caching), Q3 (rate limiting), Q6 (result highlighting)
Week 2: Q9 (error toasts), Q10 (loading states), Q15 (keyboard shortcuts)
Week 2: Q14 (count badges), Q16 (scroll indicator), Q17 (mobile sidebar)
Week 2: Q18 (session search)
```

**Total quick win effort:** ~35 hours (less than 1 week for one developer)

### 10.4 Quick Win Code Examples

#### Q1: Split app.py into routers

```python
# server/routers/chat.py
from fastapi import APIRouter
from server.app import ChatRequest, ChatResponse

router = APIRouter(prefix="/api", tags=["chat"])

@router.post("/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    # ... existing chat logic ...
    pass

@router.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    # ... existing streaming logic ...
    pass

# server/app.py (simplified)
from fastapi import FastAPI
from server.routers import chat, sessions, search, papers, wiki, settings, web

app = FastAPI(...)
app.include_router(chat.router)
app.include_router(sessions.router)
# ... etc
```

#### Q4: Improved formatMarkdown() in app.js

```javascript
function formatMarkdown(text) {
    if (!text) return '';
    let html = escapeHtml(text);

    // Code blocks with language
    html = html.replace(/```(\w+)?\n([\s\S]*?)```/g, (_, lang, code) => {
        const cls = lang ? ` class="language-${lang}"` : '';
        return `<pre><code${cls}>${code.trim()}</code></pre>`;
    });

    // Inline code
    html = html.replace(/`([^`]+)`/g, '<code>$1</code>');

    // Bold and italic
    html = html.replace(/\*\*\*(.+?)\*\*\*/g, '<strong><em>$1</em></strong>');
    html = html.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/\*(.+?)\*/g, '<em>$1</em>');

    // Headers
    html = html.replace(/^### (.+)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.+)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.+)$/gm, '<h1>$1</h1>');

    // Tables
    html = html.replace(/\|(.+)\|\n\|[-| ]+\|\n((?:\|.+\|\n?)*)/g, (_, header, body) => {
        const headers = header.split('|').map(h => `<th>${h.trim()}</th>`).join('');
        const rows = body.trim().split('\n').map(row => {
            const cells = row.split('|').map(c => `<td>${c.trim()}</td>`).join('');
            return `<tr>${cells}</tr>`;
        }).join('');
        return `<table><thead><tr>${headers}</tr></thead><tbody>${rows}</tbody></table>`;
    });

    // Unordered lists
    html = html.replace(/^- (.+)$/gm, '<li>$1</li>');
    html = html.replace(/(<li>.*<\/li>\n?)+/g, '<ul>$&</ul>');

    // Ordered lists
    html = html.replace(/^\d+\. (.+)$/gm, '<li>$1</li>');

    // Paragraphs
    html = html.replace(/\n\n/g, '</p><p>');
    html = html.replace(/\n/g, '<br>');
    html = `<p>${html}</p>`;

    return html;
}
```

---

## Appendix A: Phase Dependency Graph

```
Phase 1: Frontend Migration
    │
    ├──▶ Phase 2: Semantic Search
    │       │
    │       ├──▶ Phase 3: Knowledge Graph
    │       │       │
    │       │       └──▶ Phase 4: Agent Swarm
    │       │               │
    │       │               └──▶ Phase 5: Workflow Engine
    │       │
    │       └──▶ Phase 6: Multi-Source Ingestion
    │
    └──▶ Phase 7: Tools & Polish (depends on ALL phases)
```

## Appendix B: Estimated Timeline

| Phase | Duration | Start | End | Cumulative |
|-------|----------|-------|-----|------------|
| Quick Wins | 1 week | Week 0 | Week 1 | 1 week |
| Phase 1 | 3 weeks | Week 1 | Week 4 | 4 weeks |
| Phase 2 | 2 weeks | Week 4 | Week 6 | 6 weeks |
| Phase 3 | 2 weeks | Week 6 | Week 8 | 8 weeks |
| Phase 4 | 3 weeks | Week 8 | Week 11 | 11 weeks |
| Phase 5 | 2 weeks | Week 11 | Week 13 | 13 weeks |
| Phase 6 | 2 weeks | Week 13 | Week 15 | 15 weeks |
| Phase 7 | 2 weeks | Week 15 | Week 17 | 17 weeks |

**Total estimated duration:** 17 weeks (~4 months) for a single developer
**With 2 developers:** ~10-12 weeks (parallel work on frontend + backend)

## Appendix C: Total Task Count

| Phase | Tasks | Estimated Hours |
|-------|-------|----------------|
| Quick Wins | 18 | 35h |
| Phase 1 | 18 | 56h |
| Phase 2 | 10 | 27h |
| Phase 3 | 12 | 42h |
| Phase 4 | 15 | 56h |
| Phase 5 | 14 | 46h |
| Phase 6 | 12 | 41h |
| Phase 7 | 15 | 52h |
| **Total** | **114** | **355h** |

---

*This plan was generated on 2026-05-18 by the Architecture Agent. Review and adjust estimates based on team capacity and priorities.*