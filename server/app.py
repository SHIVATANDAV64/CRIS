"""
CRIS Web Server — FastAPI backend for the research chat interface.

Run with:
    python -m uvicorn server.app:app --reload --port 8000
"""
import sys
import uuid
import json
import re
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

from config.settings import CONTEXT_ENTRIES_LIMIT, MAX_THINKING_LENGTH, get_config, update_config, reset_config
from core.search_engine import search, get_stats, create_index, get_all_entries
from core.model_client import ModelClient
from core.chat_store import (
    init_chat_store,
    create_session,
    get_session,
    update_session_title,
    delete_session,
    list_sessions,
    add_message,
    get_messages,
    format_history_for_prompt,
)
from core.domain_manager import (
    get_domains,
    get_papers_for_domain,
    get_paper_detail,
    migrate_existing_papers,
    get_raw_sources as load_raw_sources,
    get_paper_by_id,
)
from core.chat_memory import extract_and_store_memory
from core.wiki_manager import WikiManager
from core.web_tools import get_scraper, get_search
from config.settings import WIKI_DIR

# ── App Setup ────────────────────────────────────────────────────────────

app = FastAPI(
    title="CRIS — Cross-Domain Research Intelligence System",
    description="AI-powered research assistant for cross-domain discovery",
    version="2.0.0",
)

# Static files and templates
STATIC_DIR = Path(__file__).parent / "static"
TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR.mkdir(exist_ok=True)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))

# Lazy-loaded model clients (one per backend)
_model_clients: dict[str, ModelClient] = {}


def get_model_client(model_id: Optional[str] = None) -> ModelClient:
    """Lazy-load the model client for the requested backend."""
    global _model_clients
    key = model_id or "darwin-opus"
    if key not in _model_clients:
        try:
            _model_clients[key] = ModelClient(model_id=model_id)
        except Exception as e:
            print(f"Warning: Could not initialize model client ({key}): {e}")
            print("Chat will work in search-only mode.")
    return _model_clients[key]


# ── Request/Response Models ──────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    use_reasoning: bool = True
    source_papers: Optional[list[str]] = None  # arxiv_ids of papers to use as context
    model_id: Optional[str] = None  # 'darwin-opus' or 'minimax-m2.5'


class ChatResponse(BaseModel):
    response: str
    thinking: str = ""
    sources: list[dict] = []
    tokens_used: int = 0
    mode: str = ""
    session_id: str = ""


class SettingsUpdate(BaseModel):
    updates: dict


class SessionCreate(BaseModel):
    title: Optional[str] = "New Chat"


class SessionTitleUpdate(BaseModel):
    title: str


class WebSearchRequest(BaseModel):
    query: str
    num_results: int = 5


class WebScrapeRequest(BaseModel):
    url: str


# ── Routes ───────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize search index and chat store on startup."""
    create_index()
    init_chat_store()


@app.get("/")
async def index(request: Request):
    """Serve the chat interface."""
    return templates.TemplateResponse(request, "index.html")


# ── Intent Detection ─────────────────────────────────────────────────────

_NON_RESEARCH_PATTERNS = [
    r'^\s*(hi|hello|hey|howdy|greetings|good\s*(morning|afternoon|evening|night))[\s!.,]*$',
    r'^\s*how\s+(are\s+you|is\s+(it|the\s+day|things|life)|do\s+(you|u)\s+(do|feel))[\s?!.]*$',
    r"^\s*(what'?s?\s+up|sup|yo|hey\s+there|hi\s+there)[\s!.,?]*$",
    r'^\s*(thanks?|thank\s+you|thx|ty)[\s!.,]*$',
    r'^\s*(bye|goodbye|see\s+you|later|cya)[\s!.,]*$',
    r'^\s*(help|what\s+can\s+you\s+do|what\s+do\s+you\s+do)[\s?!.]*$',
    r'^\s*(who\s+are\s+you|what\s+are\s+you|tell\s+me\s+about\s+yourself)[\s?!.]*$',
    r'^\s*(tell\s+me\s+a\s+(joke|story)|make\s+me\s+laugh)[\s?!.]*$',
    r'^\s*(what\s+(time|day|date)\s+is\s+(it|now|today))[\s?!.]*$',
]

_RESEARCH_INDICATORS = [
    'paper', 'research', 'study', 'method', 'algorithm', 'model', 'neural',
    'network', 'learning', 'domain', 'cross-domain', 'transfer', 'mechanism',
    'compare', 'difference', 'similar', 'connection', 'relation', 'analysis',
    'explain', 'how does', 'what is', 'why', 'summarize', 'review',
    'arxiv', 'citation', 'experiment', 'dataset', 'performance', 'accuracy',
    'technique', 'approach', 'framework', 'system', 'architecture',
]


def _is_research_query(query: str) -> bool:
    """Check if a query is research-oriented vs casual conversation."""
    q_lower = query.lower().strip()

    for pattern in _NON_RESEARCH_PATTERNS:
        if re.match(pattern, q_lower):
            return False

    if len(q_lower.split()) <= 3:
        return False

    for indicator in _RESEARCH_INDICATORS:
        if indicator in q_lower:
            return True

    return len(q_lower.split()) >= 5


# ── Chat Endpoints ───────────────────────────────────────────────────────

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    query = req.message.strip()
    if not query:
        return ChatResponse(response="Please ask a research question.")

    session_id = req.session_id or str(uuid.uuid4())

    session = get_session(session_id)
    if not session:
        title = query[:50] + ("..." if len(query) > 50 else "")
        create_session(session_id, title)

    add_message(session_id, "user", query)

    is_research = _is_research_query(query)

    if req.source_papers:
        results = []
        for arxiv_id in req.source_papers:
            paper_results = search(arxiv_id, limit=5)
            if paper_results:
                results.extend(paper_results)
            else:
                raw_paper = get_paper_by_id(arxiv_id)
                if raw_paper:
                    authors = [a for a in raw_paper.get('authors', []) if a]
                    wiki_content = f"# {raw_paper['title']}\n\n**arXiv ID**: {raw_paper['arxiv_id']}\n**Categories**: {raw_paper.get('categories', '')}\n**Authors**: {', '.join(authors)}\n\n## Abstract\n{raw_paper.get('abstract', '')}\n"
                    results.append({
                        "arxiv_id": raw_paper["arxiv_id"],
                        "title": raw_paper["title"],
                        "contribution_type": "",
                        "domains": raw_paper.get("categories", ""),
                        "categories": raw_paper.get("categories", ""),
                        "date_published": raw_paper.get("created", "")[:10],
                        "wiki_content": wiki_content,
                        "cross_domain_tags": "",
                        "relevance": 0,
                    })
        seen = set()
        unique_results = []
        for r in results:
            if r["arxiv_id"] not in seen:
                seen.add(r["arxiv_id"])
                unique_results.append(r)
        results = unique_results
    elif is_research:
        results = search(query, limit=CONTEXT_ENTRIES_LIMIT)
    else:
        results = []

    sources = [
        {
            "arxiv_id": r["arxiv_id"],
            "title": r["title"],
            "contribution_type": r.get("contribution_type", ""),
            "domains": r.get("domains", ""),
        }
        for r in results
    ]

    history_context = format_history_for_prompt(session_id)

    if req.use_reasoning:
            client = get_model_client(req.model_id)
            if client:
                result = client.generate(
                    user_message=query,
                    wiki_context=results if is_research else None,
                    conversation_history=history_context,
                )

                add_message(
                    session_id,
                    "assistant",
                    result["response"],
                    thinking=result.get("thinking", ""),
                    sources=sources,
                )

                try:
                    extract_and_store_memory(
                        user_message=query,
                        assistant_response=result["response"],
                        session_id=session_id,
                        wiki_dir=WIKI_DIR,
                        sources=sources,
                    )
                except Exception as e:
                    print(f"Memory extraction failed: {e}")

                return ChatResponse(
                    response=result["response"],
                    thinking=result.get("thinking", ""),
                    sources=sources,
                    tokens_used=result.get("tokens_used", 0),
                    mode=result.get("mode", ""),
                    session_id=session_id,
                )

    summary = f"Found {len(results)} relevant papers:\n\n"
    for i, r in enumerate(results, 1):
        summary += f"**{i}. {r['title']}** ({r['arxiv_id']})\n"
        content_preview = r.get("wiki_content", "")[:200]
        summary += f"  {content_preview}...\n\n"

    add_message(session_id, "assistant", summary)

    return ChatResponse(
        response=summary,
        sources=sources,
        mode="search-only",
        session_id=session_id,
    )


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    query = req.message.strip()
    if not query:
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'content': 'Please ask a research question.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    session_id = req.session_id or str(uuid.uuid4())

    session = get_session(session_id)
    if not session:
        title = query[:50] + ("..." if len(query) > 50 else "")
        create_session(session_id, title)

    add_message(session_id, "user", query)

    is_research = _is_research_query(query)

    if req.source_papers:
        results = []
        for arxiv_id in req.source_papers:
            paper_results = search(arxiv_id, limit=5)
            if paper_results:
                results.extend(paper_results)
            else:
                raw_paper = get_paper_by_id(arxiv_id)
                if raw_paper:
                    authors = [a for a in raw_paper.get('authors', []) if a]
                    wiki_content = f"# {raw_paper['title']}\n\n**arXiv ID**: {raw_paper['arxiv_id']}\n**Categories**: {raw_paper.get('categories', '')}\n**Authors**: {', '.join(authors)}\n\n## Abstract\n{raw_paper.get('abstract', '')}\n"
                    results.append({
                        "arxiv_id": raw_paper["arxiv_id"],
                        "title": raw_paper["title"],
                        "contribution_type": "",
                        "domains": raw_paper.get("categories", ""),
                        "categories": raw_paper.get("categories", ""),
                        "date_published": raw_paper.get("created", "")[:10],
                        "wiki_content": wiki_content,
                        "cross_domain_tags": "",
                        "relevance": 0,
                    })
        seen = set()
        unique_results = []
        for r in results:
            if r["arxiv_id"] not in seen:
                seen.add(r["arxiv_id"])
                unique_results.append(r)
        results = unique_results
    elif is_research:
        results = search(query, limit=CONTEXT_ENTRIES_LIMIT)
    else:
        results = []

    sources = [
        {
            "arxiv_id": r["arxiv_id"],
            "title": r["title"],
            "contribution_type": r.get("contribution_type", ""),
            "domains": r.get("domains", ""),
        }
        for r in results
    ]

    history_context = format_history_for_prompt(session_id)

    async def generate_stream():
        if sources:
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'session_id': session_id})}\n\n"

        if req.use_reasoning:
            client = get_model_client(req.model_id)
            if client:
                full_response = ""
                stream_timed_out = False

                try:
                    for chunk in client.generate_stream(
                        user_message=query,
                        wiki_context=results if is_research else None,
                        conversation_history=history_context,
                    ):
                        full_response += chunk
                        if chunk:
                            yield f"data: {json.dumps({'type': 'content', 'content': chunk})}\n\n"
                except Exception as e:
                    print(f"[chat_stream] Streaming error: {e}")
                    if not full_response:
                        yield f"data: {json.dumps({'type': 'content', 'content': f'**Error**: {str(e)}'})}\n\n"
                    stream_timed_out = True

                if full_response or stream_timed_out:
                    add_message(
                        session_id,
                        "assistant",
                        full_response if full_response else f"Error: {str(e) if 'e' in dir() else 'Stream failed'}",
                        sources=sources,
                    )

                    try:
                        extract_and_store_memory(
                            user_message=query,
                            assistant_response=full_response,
                            session_id=session_id,
                            wiki_dir=WIKI_DIR,
                            sources=sources,
                        )
                    except Exception as e:
                        print(f"Memory extraction failed: {e}")

        else:
            summary = f"Found {len(results)} relevant papers:\n\n"
            for i, r in enumerate(results, 1):
                summary += f"**{i}. {r['title']}** ({r['arxiv_id']})\n"
                content_preview = r.get("wiki_content", "")[:200]
                summary += f"  {content_preview}...\n\n"

            add_message(session_id, "assistant", summary)
            yield f"data: {json.dumps({'type': 'content', 'content': summary})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


# ── Session Management Endpoints ─────────────────────────────────────────

@app.get("/api/sessions")
async def get_sessions(limit: int = 50, offset: int = 0):
    """List all chat sessions."""
    sessions = list_sessions(limit=limit, offset=offset)
    return {"count": len(sessions), "sessions": sessions}


@app.post("/api/sessions")
async def create_new_session(req: SessionCreate):
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    session = create_session(session_id, req.title or "New Chat")
    return session


@app.get("/api/sessions/{session_id}")
async def get_session_messages(session_id: str):
    """Get all messages for a session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = get_messages(session_id)
    return {"session": session, "messages": messages}


@app.get("/api/sessions/{session_id}/export")
async def export_session(session_id: str):
    """Export a session as a downloadable JSON file."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = get_messages(session_id)
    export_data = {
        "session": session,
        "messages": messages,
        "exported_at": datetime.now().isoformat(),
    }

    return JSONResponse(
        content=export_data,
        headers={
            "Content-Disposition": f'attachment; filename="cris-session-{session_id[:8]}.json"',
        },
    )


@app.patch("/api/sessions/{session_id}")
async def update_session(session_id: str, req: SessionTitleUpdate):
    """Update a session's title."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    update_session_title(session_id, req.title)
    return {"id": session_id, "title": req.title}


@app.delete("/api/sessions/{session_id}")
async def delete_session_endpoint(session_id: str):
    """Delete a session and all its messages."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    delete_session(session_id)
    return {"deleted": session_id}


# ── Raw Sources / Domain Endpoints ───────────────────────────────────────

@app.get("/api/domains")
async def list_domains():
    """List all domains with paper counts."""
    domains = get_domains()
    return {"count": len(domains), "domains": domains}


@app.get("/api/domains/{domain}/papers")
async def get_domain_papers(domain: str):
    """Get all papers for a domain, grouped by date."""
    papers = get_papers_for_domain(domain)
    return {"domain": domain, "date_groups": papers}


@app.get("/api/domains/{domain}/papers/{date}/{paper_id}")
async def get_paper(domain: str, date: str, paper_id: str):
    """Get a specific paper's full details."""
    paper = get_paper_detail(domain, date, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@app.post("/api/raw-sources/migrate")
async def migrate_sources():
    """Migrate existing papers from date-based to domain-based storage."""
    counts = migrate_existing_papers()
    return {"migrated": counts, "total": sum(counts.values())}


@app.get("/api/raw-sources")
async def list_raw_sources():
    """Get all raw papers organized by date and category."""
    sources = load_raw_sources()
    return {"count": sum(g["paper_count"] for g in sources), "date_groups": sources}


@app.get("/api/raw-sources/{arxiv_id}")
async def get_raw_paper(arxiv_id: str):
    """Get a specific raw paper by arXiv ID."""
    paper = get_paper_by_id(arxiv_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


# ── Settings Endpoints ───────────────────────────────────────────────────

@app.get("/api/models")
async def list_models():
    """List available models for the model selector."""
    return {
        "models": [
            {
                "id": "darwin-opus",
                "name": "Darwin-36B-Opus",
                "provider": "Modal",
                "description": "Fine-tuned Qwen3.6-35B-A3B for research reasoning",
            },
            {
                "id": "minimax-m2.5",
                "name": "MiniMax M2.5",
                "provider": "Bedrock",
                "description": "AWS Bedrock hosted MiniMax model",
            },
        ],
        "default": "darwin-opus",
    }


@app.get("/api/settings")
async def get_settings():
    """Get current configuration."""
    config = get_config()
    return {"config": config}


@app.post("/api/settings")
async def update_settings(req: SettingsUpdate):
    """Update configuration."""
    config = update_config(req.updates)
    return {"config": config}


@app.post("/api/settings/reset")
async def reset_settings():
    """Reset configuration to defaults."""
    config = reset_config()
    return {"config": config}


# ── Stats & Search Endpoints ─────────────────────────────────────────────

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


# ── Memory & Wiki Endpoints ───────────────────────────────────────────────

@app.post("/api/memory/extract")
async def extract_memory(req: ChatRequest):
    """Manually trigger memory extraction for a conversation."""
    session_id = req.session_id
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id required")

    messages = get_messages(session_id, limit=2)
    if len(messages) < 2:
        return {"status": "no_conversation", "message": "Need at least one exchange"}

    user_msg = messages[-2] if messages[-2]["role"] == "user" else None
    assistant_msg = messages[-1] if messages[-1]["role"] == "assistant" else None

    if not user_msg or not assistant_msg:
        return {"status": "no_exchange", "message": "Need user+assistant exchange"}

    result = extract_and_store_memory(
        user_message=user_msg["content"],
        assistant_response=assistant_msg["content"],
        session_id=session_id,
        wiki_dir=WIKI_DIR,
        sources=assistant_msg.get("sources", []),
    )

    return {"status": "success", "result": result}


@app.get("/api/wiki/stats")
async def wiki_stats():
    """Get wiki knowledge base statistics."""
    wiki_manager = WikiManager(WIKI_DIR)

    sources = wiki_manager.get_all_sources()
    notes = wiki_manager.get_notes()
    concepts = list(wiki_manager.concepts_dir.glob("*.md"))
    entities = list(wiki_manager.entities_dir.glob("*.md"))

    return {
        "sources": len(sources),
        "concepts": len(concepts),
        "entities": len(entities),
        "notes": len(notes),
        "last_updated": datetime.now().isoformat(),
    }


@app.post("/api/wiki/rebuild")
async def wiki_rebuild():
    """Rebuild wiki structure (summaries, graph, etc.)."""
    wiki_manager = WikiManager(WIKI_DIR)
    wiki_manager.rebuild_all()
    return {"status": "success"}


@app.get("/api/wiki/entities")
async def wiki_entities():
    """List all extracted entities."""
    wiki_manager = WikiManager(WIKI_DIR)
    entities = []
    for f in wiki_manager.entities_dir.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        fm, body = wiki_manager.parse_frontmatter(content)
        entities.append({
            "name": fm.get("name", f.stem),
            "type": fm.get("type", "term"),
            "mentions": fm.get("mentions", 0),
            "first_seen": fm.get("first_seen", ""),
        })
    return {"count": len(entities), "entities": entities}


@app.get("/api/wiki/notes")
async def wiki_notes():
    """List all conversation notes."""
    wiki_manager = WikiManager(WIKI_DIR)
    notes = []
    for f in wiki_manager.notes_dir.glob("*.md"):
        content = f.read_text(encoding="utf-8")
        fm, body = wiki_manager.parse_frontmatter(content)
        notes.append({
            "title": fm.get("title", f.stem),
            "date": fm.get("date", ""),
            "session_id": fm.get("session_id", ""),
        })
    return {"count": len(notes), "notes": notes}


# ── Web Search & Scraper Endpoints ────────────────────────────────────────

@app.post("/api/web/search")
async def web_search(req: WebSearchRequest):
    """Search the web for a query."""
    search = get_search()
    results = await search.search(req.query, req.num_results)
    return {"query": req.query, "count": len(results), "results": results}


@app.post("/api/web/scrape")
async def web_scrape(req: WebScrapeRequest):
    """Scrape a URL and return cleaned content."""
    scraper = get_scraper()
    result = await scraper.scrape_url(req.url)
    return result


@app.post("/api/web/search-and-scrape")
async def web_search_and_scrape(req: WebSearchRequest):
    """Search the web and scrape top results."""
    search = get_search()
    results = await search.search_and_scrape(req.query, req.num_results)
    return {"query": req.query, "count": len(results), "results": results}
