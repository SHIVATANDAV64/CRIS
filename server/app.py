"""
CRIS Web Server — FastAPI backend for the research chat interface.

Run with:
    python -m uvicorn server.app:app --reload --port 8000
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from config.settings import SERVER_HOST, SERVER_PORT, CONTEXT_ENTRIES_LIMIT
from core.search_engine import search, get_stats, create_index, get_all_entries
from core.model_client import ModelClient

# ── App Setup ────────────────────────────────────────────────────────────

app = FastAPI(
    title="CRIS — Cross-Domain Research Intelligence System",
    description="AI-powered research assistant for cross-domain discovery",
    version="1.0.0",
)

# Static files and templates
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Lazy-loaded model client (initialized on first request)
_model_client = None


def get_model_client() -> ModelClient:
    """Lazy-load the model client."""
    global _model_client
    if _model_client is None:
        try:
            _model_client = ModelClient()
        except Exception as e:
            print(f"Warning: Could not initialize model client: {e}")
            print("Chat will work in search-only mode.")
    return _model_client


# ── Request/Response Models ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    use_reasoning: bool = True  # Whether to use zira-researcher or just search


class ChatResponse(BaseModel):
    response: str
    thinking: str = ""
    sources: list[dict] = []
    tokens_used: int = 0
    mode: str = ""


# ── Routes ───────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    """Initialize search index on startup."""
    create_index()


@app.get("/")
async def index(request: Request):
    """Serve the chat interface."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main chat endpoint.

    Flow:
    1. Search wiki for relevant entries
    2. Feed context + question to zira-researcher
    3. Return reasoning + response + citations
    """
    query = req.message.strip()
    if not query:
        return ChatResponse(response="Please ask a research question.")

    # Step 1: Search wiki for relevant context
    results = search(query, limit=CONTEXT_ENTRIES_LIMIT)

    if not results:
        return ChatResponse(
            response="No relevant papers found in the knowledge base. Try a different query, or ingest more papers.",
            sources=[],
        )

    # Format sources for citation
    sources = [
        {
            "arxiv_id": r["arxiv_id"],
            "title": r["title"],
            "contribution_type": r.get("contribution_type", ""),
            "domains": r.get("domains", ""),
        }
        for r in results
    ]

    # Step 2: Generate reasoning response (if model available)
    if req.use_reasoning:
        client = get_model_client()
        if client:
            result = client.generate(
                user_message=query,
                wiki_context=results,
            )
            return ChatResponse(
                response=result["response"],
                thinking=result.get("thinking", ""),
                sources=sources,
                tokens_used=result.get("tokens_used", 0),
                mode=result.get("mode", ""),
            )

    # Fallback: return search results without reasoning
    summary = f"Found {len(results)} relevant papers:\n\n"
    for i, r in enumerate(results, 1):
        summary += f"**{i}. {r['title']}** ({r['arxiv_id']})\n"
        # Show first 200 chars of wiki content
        content_preview = r.get("wiki_content", "")[:200]
        summary += f"  {content_preview}...\n\n"

    return ChatResponse(
        response=summary,
        sources=sources,
        mode="search-only",
    )


@app.get("/api/stats")
async def stats():
    """Get knowledge base statistics."""
    return get_stats()


@app.get("/api/search")
async def search_papers(q: str, limit: int = 20):
    """Direct search endpoint."""
    results = search(q, limit=limit)
    return {"query": q, "count": len(results), "results": results}


@app.get("/api/papers")
async def list_papers(limit: int = 50):
    """List all papers in the knowledge base."""
    entries = get_all_entries()
    return {"count": len(entries), "papers": entries[:limit]}
