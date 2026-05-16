# CRIS — Cross-Domain Research Intelligence System

An AI-powered research intelligence system that ingests scientific papers from arXiv, compiles them into a structured wiki knowledge base, and provides a reasoning-powered chat interface for cross-domain discovery.

**BCA Final Semester Project | 2025-26**

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│   arXiv (OAI)   │────▶│  Wiki Compiler   │────▶│  Knowledge Wiki │
│   Raw Papers    │     │  (Amazon Bedrock) │     │  sources/       │
│   data/raw/     │     │                  │     │  concepts/      │
└─────────────────┘     └──────────────────┘     │  index.md       │
                                                  └────────┬────────┘
                                                           │
                                                  ┌────────▼────────┐
                                                  │  SQLite FTS5    │
                                                  │  Search Index   │
                                                  └────────┬────────┘
                                                           │
┌─────────────────┐     ┌──────────────────┐     ┌────────▼────────┐
│   Web Browser   │◀───▶│   FastAPI Server  │◀───▶│  Reasoning AI   │
│   Chat UI       │     │   localhost:8000  │     │  Amazon Bedrock  │
└─────────────────┘     └──────────────────┘     └─────────────────┘
```

### Three Modules

1. **Ingestion Pipeline** — Fetches papers from arXiv via OAI-PMH (Sickle library), stores metadata as JSON.
2. **Wiki Compiler & Search** — Compiles papers into structured wiki pages using LLM, builds concept pages that aggregate across papers, indexes everything in SQLite FTS5.
3. **Research Chat Assistant** — FastAPI web interface with conversation memory. Searches the wiki, builds context, sends to reasoning model, returns cited answers.

### Wiki Structure (Karpathy LLM Wiki Pattern)

```
data/wiki/
├── schema.md        # Rules and conventions
├── index.md         # Master catalog of all pages
├── log.md           # Chronological operation log
├── sources/         # Per-paper summaries (LLM-generated)
├── concepts/        # Cross-paper concept aggregations
└── entities/        # Named entity pages
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- An [Amazon Bedrock API key](https://console.aws.amazon.com/bedrock/) with MiniMax M2.5 model access enabled

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

Create a `.env` file in the project root:

```env
BEDROCK_API_KEY=your_bedrock_api_key_here
BEDROCK_REGION=us-east-1
```

### 3. Ingest papers from arXiv

```bash
python scripts/ingest_arxiv.py --days 7 --max 50
```

### 4. Compile wiki entries

```bash
python scripts/compile_wiki.py --all --max 30
```

### 5. Build wiki structure & search index

```bash
python scripts/build_wiki.py
python scripts/build_index.py --rebuild
```

### 6. Start the web server

```bash
python -m uvicorn server.app:app --port 8000
```

Open `http://127.0.0.1:8000` in your browser.

---

## Technology Stack

| Component | Technology |
|-----------|-----------|
| Backend & API | Python, FastAPI, Uvicorn |
| Data Ingestion | Sickle (OAI-PMH) |
| Database & Search | SQLite3 + FTS5 (BM25 ranking) |
| Wiki Compilation | Amazon Bedrock (MiniMax M2.5) |
| Reasoning Inference | Amazon Bedrock (MiniMax M2.5) |
| Frontend | HTML5, CSS3, JavaScript |

---

## Scripts Reference

| Script | Purpose |
|--------|---------|
| `scripts/ingest_arxiv.py` | Fetch papers from arXiv |
| `scripts/compile_wiki.py` | Compile papers into wiki source pages |
| `scripts/build_wiki.py` | Build concept pages, index, and log |
| `scripts/build_index.py` | Populate SQLite FTS5 search index |
| `scripts/lint_wiki.py` | Health-check the wiki for broken links and orphans |

---

## Limitations

- Search is keyword-based (BM25), not semantic. Cross-domain queries using different vocabulary may not match.
- Reasoning quality depends on the model used and the context window.
- Free API tiers have rate limits; large batch compilations may take time.
- This is a research assistance tool, not a definitive oracle.

---

## License

BCA Final Semester Academic Project.
