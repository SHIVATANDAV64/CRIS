"""
CRIS Web Server — FastAPI backend for the research chat interface.

Run with:
    python -m uvicorn server.app:app --reload --port 8000
"""
import sys
import uuid
import json
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

from config.settings import CONTEXT_ENTRIES_LIMIT, get_config, update_config, reset_config
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

# Lazy-loaded model client
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
    session_id: Optional[str] = None
    use_reasoning: bool = True
    source_papers: Optional[list[str]] = None  # arxiv_ids of papers to use as context


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

    # If source papers are explicitly provided, use only those
    if req.source_papers:
        results = []
        for arxiv_id in req.source_papers:
            # First try wiki DB
            paper_results = search(arxiv_id, limit=5)
            if paper_results:
                results.extend(paper_results)
            else:
                # Fallback: load raw paper JSON and create a temporary wiki-like entry
                raw_paper = get_paper_by_id(arxiv_id)
                if raw_paper:
                    wiki_content = f"# {raw_paper['title']}\n\n**arXiv ID**: {raw_paper['arxiv_id']}\n**Categories**: {raw_paper.get('categories', '')}\n**Authors**: {', '.join(raw_paper.get('authors', []))}\n\n## Abstract\n{raw_paper.get('abstract', '')}\n"
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
        # Deduplicate
        seen = set()
        unique_results = []
        for r in results:
            if r["arxiv_id"] not in seen:
                seen.add(r["arxiv_id"])
                unique_results.append(r)
        results = unique_results
    else:
        # No explicit sources — search wiki for relevant entries
        results = search(query, limit=CONTEXT_ENTRIES_LIMIT)

    if not results:
        response_text = "No relevant papers found in the knowledge base. Try a different query, or ingest more papers."
        add_message(session_id, "assistant", response_text)
        return ChatResponse(
            response=response_text,
            sources=[],
            session_id=session_id,
        )

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
        client = get_model_client()
        if client:
            result = client.generate(
                user_message=query,
                wiki_context=results,
                conversation_history=history_context,
            )

            add_message(
                session_id,
                "assistant",
                result["response"],
                thinking=result.get("thinking", ""),
                sources=sources,
            )

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

    # If source papers are explicitly provided, use only those
    if req.source_papers:
        results = []
        for arxiv_id in req.source_papers:
            paper_results = search(arxiv_id, limit=5)
            if paper_results:
                results.extend(paper_results)
            else:
                raw_paper = get_paper_by_id(arxiv_id)
                if raw_paper:
                    wiki_content = f"# {raw_paper['title']}\n\n**arXiv ID**: {raw_paper['arxiv_id']}\n**Categories**: {raw_paper.get('categories', '')}\n**Authors**: {', '.join(raw_paper.get('authors', []))}\n\n## Abstract\n{raw_paper.get('abstract', '')}\n"
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
    else:
        results = search(query, limit=CONTEXT_ENTRIES_LIMIT)

    if not results:
        async def no_results_stream():
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            yield f"data: {json.dumps({'type': 'content', 'content': 'No relevant papers found in the knowledge base. Try a different query, or ingest more papers.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_results_stream(), media_type="text/event-stream")

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
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'session_id': session_id})}\n\n"

        if req.use_reasoning:
            client = get_model_client()
            if client:
                full_response = ""
                thinking_content = ""
                answer_content = ""
                phase = "thinking"
                thinking_length = 0
                max_thinking_length = 2000

                for chunk in client.generate_stream(
                    user_message=query,
                    wiki_context=results,
                    conversation_history=history_context,
                ):
                    full_response += chunk

                    if phase == "thinking":
                        thinking_content = chunk
                        thinking_length = len(thinking_content)

                        transition_patterns = [
                            "\n\nFinal Answer:",
                            "\n\nAnswer:",
                            "\n\nResponse:",
                            "\n\nBased on the",
                            "\n\nIn summary",
                            "\n\nTo conclude",
                            "\n\nThe main",
                            "\n\nFrom this",
                            "\n\nGiven the",
                            "\n\nTherefore",
                            "\n\nThus",
                            "\n\nHence",
                            "\n\nIn conclusion",
                            "\n\nTo summarize",
                            "\n\nThe key findings",
                            "\n\nBased on my analysis",
                        ]

                        transitioned = False
                        for pattern in transition_patterns:
                            if pattern in chunk:
                                split_idx = chunk.find(pattern)
                                thinking_content = chunk[:split_idx]
                                answer_content = chunk[split_idx:]
                                phase = "answer"
                                transitioned = True

                                if thinking_content.strip():
                                    yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_content})}\n\n"
                                if answer_content.strip():
                                    yield f"data: {json.dumps({'type': 'content', 'content': answer_content})}\n\n"
                                break

                        if not transitioned:
                            if thinking_length > max_thinking_length:
                                phase = "answer"
                                answer_content = "\n\nBased on my analysis of the provided research papers, here are the key cross-domain applications and insights:\n\n"
                                yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_content})}\n\n"
                                yield f"data: {json.dumps({'type': 'content', 'content': answer_content})}\n\n"
                            else:
                                if thinking_content.strip():
                                    yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_content})}\n\n"

                    elif phase == "answer":
                        answer_content = chunk
                        if answer_content.strip():
                            yield f"data: {json.dumps({'type': 'content', 'content': answer_content})}\n\n"

                if phase == "thinking" and thinking_content.strip():
                    conclusion = "\n\nBased on my analysis, the provided research papers demonstrate several cross-domain applications and mechanisms that can be mapped across different scientific fields."
                    yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_content})}\n\n"
                    yield f"data: {json.dumps({'type': 'content', 'content': conclusion})}\n\n"
                    full_response += conclusion
                elif phase == "answer" and answer_content.strip():
                    yield f"data: {json.dumps({'type': 'content', 'content': answer_content})}\n\n"

                add_message(
                    session_id,
                    "assistant",
                    full_response,
                    thinking=thinking_content,
                    sources=sources,
                )

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
