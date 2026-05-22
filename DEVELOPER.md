# CRIS: Developer & Systems Engineering Manual

Welcome to the CRIS Developer Manual. This document contains the technical details regarding the codebase architecture, database schemas, API routers, background task execution, local configuration, and Modal.com deployment steps.

---

## 🛠️ Folder Structure & Codebase Map

```
CRIS-Start/
├── config/
│   ├── settings.py           # Configuration provider & path resolver
│   └── user_config.json      # Dynamic settings (overrides settings.py defaults)
├── core/
│   ├── arxiv_client.py       # arXiv OAI-PMH XML harvester using Sickle
│   ├── chat_memory.py        # Entity, claim, and note extractor for live chat
│   ├── domain_manager.py     # Organization rules for domain folders
│   ├── embedding_client.py   # Modal embeddings interface & sqlite-vec client
│   ├── model_client.py       # Unified LLM inference routing & stream parsing
│   ├── search_engine.py      # SQLite FTS5 index builder & keyword searcher
│   ├── search_proxy.py       # SearXNG web search aggregator & quality filter
│   ├── wiki_compiler.py      # LLM-based abstract compiler
│   └── wiki_manager.py       # Obsidian cataloger & graph JSON builder
├── data/
│   ├── cris.db               # Central SQLite3 database
│   ├── ingest_status.json    # Real-time state of background scripts
│   ├── raw/                  # Harvested raw arXiv JSON metadata files
│   └── wiki/                 # Obsidian-style linked Markdown wiki
├── frontend/
│   ├── src/                  # React + Vite + TypeScript frontend
│   │   ├── components/       # UI panels (Chat, Ingest, Graph, Settings)
│   │   ├── api.ts            # Frontend Axios/fetch API client wrapper
│   │   └── App.tsx           # Dashboard layout and navigation
│   └── package.json          # Node dependencies & Vite scripts
├── modal_deploy/
│   ├── serve_model.py        # Darwin-36B-Opus LLM server on Modal.com
│   └── searxng_server.py     # SearXNG web search wrapper on Modal.com
├── scripts/
│   ├── ingest_arxiv.py       # Harvesting CLI tool
│   ├── compile_wiki.py       # Paper compilation CLI tool
│   ├── build_wiki.py         # Concept synthesis CLI tool
│   ├── build_index.py        # Database indexing CLI tool
│   └── lint_wiki.py          # Wiki verification CLI tool
├── server/
│   ├── app.py                # FastAPI base application & mounts
│   ├── dependencies.py       # FastAPI routing dependencies
│   ├── models/schemas.py     # Pydantic exchange schemas
│   └── routers/              # API controllers (chat, search, wiki, scripts)
└── requirements.txt          # Python environments
```

---

## 💾 Database Schema Details (`data/cris.db`)

CRIS uses a single SQLite3 database (`data/cris.db`) that stores paper metadata, the FTS5 search index, embedding metadata, citation links, and research plans.

```
                  ┌───────────────────────────────┐
                  │            papers             │
                  ├───────────────────────────────┤
                  │ arxiv_id (PK)                 │◄┐
                  │ title                         │ │
                  │ wiki_content                  │ │
                  │ domains                       │ │
                  │ categories                    │ │
                  │ date_published                │ │
                  │ cross_domain_tags             │ │
                  └──────────────┬────────────────┘ │
                                 │                  │
                    (via Triggers to Sync)          │
                                 │                  │
                  ┌──────────────▼────────────────┐ │
                  │          papers_fts           │ │
                  ├───────────────────────────────┤ │
                  │ (FTS5 Virtual Table)          │ │
                  └───────────────────────────────┘ │
                                                    │
                  ┌───────────────────────────────┐ │
                  │       paper_embeddings        │ │
                  ├───────────────────────────────┤ │
                  │ arxiv_id (PK/FK)              ├─┘
                  │ has_embedding (BOOL)          │
                  │ embedding_dim (INT)           │
                  └───────────────────────────────┘
                                                    │
                  ┌───────────────────────────────┐ │
                  │         paper_vectors         │ │
                  ├───────────────────────────────┤ │
                  │ (VIRTUAL TABLE using vec0)     ├─┘
                  │ arxiv_id (PK/FK)              │
                  │ embedding float[2560]         │
                  └───────────────────────────────┘
```

### 1. Papers & Full-Text Search
*   **`papers` Table**: Contains details of compiled papers.
*   **`papers_fts` (FTS5 Virtual Table)**: Synced via three database triggers (`papers_ai` AFTER INSERT, `papers_ad` AFTER DELETE, `papers_au` AFTER UPDATE) to ensure search indices are updated automatically.

### 2. Embeddings & Vector Storage
*   **`paper_embeddings` Table**: Tracks vectorization states (flagging if a paper has an active embedding).
*   **`paper_vectors` (VIRTUAL TABLE using vec0)**: Utilizes the `sqlite-vec` extension for fast cosine-similarity indexing.
    *   *Fallback*: If the `sqlite-vec` extension is missing on the host OS, vectors are automatically written to/read from `.json` files in `data/vectors/<arxiv_id>.json` and compared using standard NumPy matrix multiplication.

### 3. Citations & Graph Edges
*   **`citations` Table**: Tracks citation relationships.
    *   `id` (INTEGER PK AUTOINCREMENT)
    *   `paper_id` (TEXT - Citing paper)
    *   `cited_paper_id` (TEXT - Cited paper)
    *   `type` (TEXT - e.g., "citation", "reference")

### 4. Structured Research Planner Tables
*   **`research_plans` Table**:
    *   `id` (TEXT PK)
    *   `title` (TEXT)
    *   `description` (TEXT)
    *   `status` (TEXT - e.g., "active", "completed")
    *   `created_at` (TIMESTAMP)
*   **`hypotheses` Table**:
    *   `id` (TEXT PK)
    *   `plan_id` (TEXT FK -> `research_plans.id`)
    *   `statement` (TEXT)
    *   `status` (TEXT - e.g., "draft", "verified", "rejected")
    *   `rationale` (TEXT)
    *   `created_at` (TIMESTAMP)
*   **`tasks` Table**:
    *   `id` (TEXT PK)
    *   `plan_id` (TEXT FK -> `research_plans.id`)
    *   `title` (TEXT)
    *   `status` (TEXT - e.g., "todo", "done")
    *   `type` (TEXT - e.g., "literature_review", "verification")
    *   `created_at` (TIMESTAMP)

---

## ⚡ Background Script Orchestrator

To prevent server blocks when performing heavy operations (like downloading papers or calling LLMs in a loop), the FastAPI backend executes CLI scripts inside background subprocesses.

The orchestrator in `server/routers/scripts.py` uses FastAPI's `BackgroundTasks`.

```
                    ┌────────────────────────────┐
                    │    FastAPI HTTP Trigger    │
                    │      /api/scripts/run      │
                    └──────────────┬─────────────┘
                                   │ (Spawns)
                                   ▼
                    ┌────────────────────────────┐
                    │     Background Subprocess  │
                    │   e.g. scripts/build_wiki  │
                    └──────────────┬─────────────┘
                                   ├─────────────────────────────┐
                                   ▼                             ▼
                    ┌────────────────────────────┐ ┌───────────────────────────┐
                    │     Writes console stdout  │ │ Updates execution lock &  │
                    │    to data/logs/<task>.log │ │ state in ingest_status.json│
                    └────────────────────────────┘ └───────────────────────────┘
```

1.  **Mutual Exclusion Locks**: Python global boolean flags (e.g., `_ingest_running`, `_compile_running`, `_build_running`) prevent concurrent execution conflicts.
2.  **Status Persistence**: The current execution status (idle, running, finished, error) is serialized to `data/ingest_status.json`.
3.  **Real-Time Logs**: Subprocess `stdout` and `stderr` are written to files inside `data/logs/`. The UI polls `/api/scripts/logs` to display live console output.

---

## ☁️ Cloud Deployments on Modal.com

CRIS utilizes serverless pipelines on [Modal.com](https://modal.com) to run the embedding client, the LLM, and the search proxy.

### 1. Serving FINAL-Bench/Darwin-36B-Opus (`modal_deploy/serve_model.py`)
This script loads the Darwin-36B-Opus model (fine-tuned from Qwen 35B) onto an RTX PRO 6000 GPU (96 GB GDDR7 VRAM).
*   **API Interface**: Exposes an OpenAI-compatible `/v1/chat/completions` endpoint.
*   **Streaming**: Utilizes Hugging Face's `TextIteratorStreamer` wrapped inside an ASGI `StreamingResponse` to deliver Server-Sent Events (SSE).
*   **Deployment Command**:
    ```bash
    modal deploy modal_deploy/serve_model.py
    ```
*   **Config Mapping**: After deployment, copy the generated Modal URL and paste it under `MODAL_API_URL` in your `.env` file.

### 2. Serving SearXNG Search Proxy (`modal_deploy/searxng_server.py`)
Instead of running a heavy local Docker container for SearXNG, CRIS deploys a lightweight aggregator on Modal that queries web APIs directly (DuckDuckGo, DDG News, arXiv, and Wikipedia) in parallel.
*   **Deployment Command**:
    ```bash
    modal deploy modal_deploy/searxng_server.py
    ```
*   **Config Mapping**: After deployment, set the generated endpoint URL as `SEARXNG_MODAL_URL` in your `.env` file.

---

## ⚙️ Environment Variables & Setup Guide

### 1. Server Environment Setup
Install the necessary python dependencies and set up your local `.env` configuration.

```bash
# Clone the repository and install packages
pip install -r requirements.txt

# Create .env from the template
cp .env.example .env
```

**`.env` File Options**:
```env
# Modal Darwin-36B-Opus Inference Endpoint
MODAL_API_URL=https://naveen95190--cris-darwin-opus-darwinopus-chat-completions.modal.run

# Amazon Bedrock Configurations
BEDROCK_API_KEY=your-bedrock-api-key-here
BEDROCK_REGION=us-east-1

# Modal SearXNG Proxy Endpoint
SEARXNG_MODAL_URL=https://your-workspace--cris-searxng-search.modal.run
```

### 2. Frontend Environment Setup
The frontend is a Vite-based React TypeScript application.

```bash
# Navigate to the frontend directory
cd frontend

# Install Node modules
npm install

# Start Vite local development server (runs on http://localhost:5173)
npm run dev

# Build production bundle (compiles to frontend/dist/)
npm run build
```

---

## 🛠️ CLI Script Reference

Developers can run core pipeline components manually using the following commands:

*   **Ingesting arXiv Papers**:
    ```bash
    # Ingest cs.AI and cs.LG papers from the past 7 days (cap at 50 papers)
    python scripts/ingest_arxiv.py --days 7 --max 50 --categories cs.AI,cs.LG
    ```
*   **Compiling Raw Papers into Wiki Pages**:
    ```bash
    # Compile all pending raw papers using the configured Bedrock model
    python scripts/compile_wiki.py --all --max 30
    ```
*   **Rebuilding concepts & wiki logs**:
    ```bash
    # Synthesize wiki concept pages and refresh master catalogs
    python scripts/build_wiki.py
    ```
*   **Indexing full-text and vector databases**:
    ```bash
    # Populate SQLite FTS5 search index tables from scratch
    python scripts/build_index.py --rebuild
    ```
*   **Linter Checks**:
    ```bash
    # Audit wiki pages for broken links, missing references, and orphans
    python scripts/lint_wiki.py
    ```

---

## 🔌 API Route Map (FastAPI Router)

| Method | Endpoint | Description |
|:---|:---|:---|
| **POST** | `/api/chat` | Synchronous reasoning chat completion |
| **POST** | `/api/chat/stream` | Streaming chat completion via SSE |
| **POST** | `/api/research/hybrid-search` | BM25 + Semantic similarity search |
| **POST** | `/api/research/cross-domain` | Cross-domain connection mapping |
| **POST** | `/api/research/decompose` | Decompose research questions into plans |
| **POST** | `/api/research/synthesize` | Aggregate claims from multiple papers |
| **GET** | `/api/research/embeddings/status` | Check vector store and index counts |
| **POST** | `/api/research/embeddings/index` | Batch vectorize pending papers |
| **GET** | `/api/wiki/graph` | Fetch Obsidian-style network metadata (`graph.json`) |
| **GET** | `/api/scripts/status` | Fetch status of background python tasks |
| **POST** | `/api/scripts/run` | Execute ingestion/compilation background tasks |
| **GET** | `/api/settings` | Read dynamically loaded configurations |
| **POST** | `/api/settings` | Save configuration overrides to user_config.json |
