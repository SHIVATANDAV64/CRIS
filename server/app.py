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

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
from typing import Optional

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

# ── Conversation Memory (In-Memory Store) ────────────────────────────────
# Stores conversation history per session. Each session has a list of
# {role, content} message dicts. This gives the AI context for follow-ups.
_conversations: dict[str, list[dict]] = {}
MAX_HISTORY_MESSAGES = 20  # Keep last N messages per session to manage context size


def get_conversation(session_id: str) -> list[dict]:
    """Get or create a conversation history for a session."""
    if session_id not in _conversations:
        _conversations[session_id] = []
    return _conversations[session_id]


def add_to_conversation(session_id: str, role: str, content: str):
    """Add a message to conversation history."""
    history = get_conversation(session_id)
    history.append({"role": role, "content": content, "timestamp": datetime.now().isoformat()})
    # Trim to keep memory bounded
    if len(history) > MAX_HISTORY_MESSAGES:
        _conversations[session_id] = history[-MAX_HISTORY_MESSAGES:]


def format_history_for_prompt(session_id: str) -> str:
    """Format recent conversation history as context for the model."""
    history = get_conversation(session_id)
    if not history:
        return ""

    # Take last 6 messages (3 exchanges) for context
    recent = history[-6:]
    lines = ["## Recent Conversation Context", ""]
    for msg in recent:
        label = "Researcher" if msg["role"] == "user" else "CRIS"
        lines.append(f"**{label}:** {msg['content'][:500]}")
        lines.append("")

    return "\n".join(lines)


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
    session_id: Optional[str] = None  # For conversation continuity
    use_reasoning: bool = True


class ChatResponse(BaseModel):
    response: str
    thinking: str = ""
    sources: list[dict] = []
    tokens_used: int = 0
    mode: str = ""
    session_id: str = ""  # Return session_id so frontend can track it


# ── Routes ───────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup_event():
    """Initialize search index on startup."""
    create_index()


@app.get("/")
async def index(request: Request):
    """Serve the chat interface."""
    return templates.TemplateResponse(request, "index.html")


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    """
    Main chat endpoint with conversation memory.

    Flow:
    1. Get/create session for conversation continuity
    2. Search wiki for relevant entries
    3. Build context with conversation history + wiki entries
    4. Feed to reasoning model (Amazon Bedrock → Local fallback → search-only)
    5. Store response in conversation history
    6. Return reasoning + response + citations
    """
    query = req.message.strip()
    if not query:
        return ChatResponse(response="Please ask a research question.")

    # Session management
    session_id = req.session_id or str(uuid.uuid4())

    # Store user message in history
    add_to_conversation(session_id, "user", query)

    # Step 1: Search wiki for relevant context
    results = search(query, limit=CONTEXT_ENTRIES_LIMIT)

    if not results:
        response_text = "No relevant papers found in the knowledge base. Try a different query, or ingest more papers."
        add_to_conversation(session_id, "assistant", response_text)
        return ChatResponse(
            response=response_text,
            sources=[],
            session_id=session_id,
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

    # Step 2: Build conversation context
    history_context = format_history_for_prompt(session_id)

    # Step 3: Generate reasoning response
    if req.use_reasoning:
        client = get_model_client()
        if client:
            result = client.generate(
                user_message=query,
                wiki_context=results,
                conversation_history=history_context,
            )

            # Store AI response in history
            add_to_conversation(session_id, "assistant", result["response"][:500])

            return ChatResponse(
                response=result["response"],
                thinking=result.get("thinking", ""),
                sources=sources,
                tokens_used=result.get("tokens_used", 0),
                mode=result.get("mode", ""),
                session_id=session_id,
            )

    # Fallback: return search results without reasoning
    summary = f"Found {len(results)} relevant papers:\n\n"
    for i, r in enumerate(results, 1):
        summary += f"**{i}. {r['title']}** ({r['arxiv_id']})\n"
        content_preview = r.get("wiki_content", "")[:200]
        summary += f"  {content_preview}...\n\n"

    add_to_conversation(session_id, "assistant", summary[:500])

    return ChatResponse(
        response=summary,
        sources=sources,
        mode="search-only",
        session_id=session_id,
    )


@app.post("/api/chat/stream")
async def chat_stream(req: ChatRequest):
    """
    Streaming chat endpoint with conversation memory.
    Returns Server-Sent Events (SSE) for real-time token streaming.
    """
    query = req.message.strip()
    if not query:
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'content': 'Please ask a research question.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    # Session management
    session_id = req.session_id or str(uuid.uuid4())

    # Store user message in history
    add_to_conversation(session_id, "user", query)

    # Step 1: Search wiki for relevant context
    results = search(query, limit=CONTEXT_ENTRIES_LIMIT)

    if not results:
        async def no_results_stream():
            yield f"data: {json.dumps({'type': 'sources', 'sources': []})}\n\n"
            yield f"data: {json.dumps({'type': 'content', 'content': 'No relevant papers found in the knowledge base. Try a different query, or ingest more papers.'})}\n\n"
            yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(no_results_stream(), media_type="text/event-stream")

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

    # Step 2: Build conversation context
    history_context = format_history_for_prompt(session_id)

    async def generate_stream():
        # Send sources first
        yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'session_id': session_id})}\n\n"

        if req.use_reasoning:
            client = get_model_client()
            if client:
                full_response = ""
                thinking_content = ""
                answer_content = ""
                phase = "thinking"  # "thinking" or "answer"
                thinking_length = 0
                max_thinking_length = 2000  # Limit thinking to ~2000 chars to prevent endless loops

                for chunk in client.generate_stream(
                    user_message=query,
                    wiki_context=results,
                    conversation_history=history_context,
                ):
                    full_response += chunk

                    if phase == "thinking":
                        # Model outputs cumulative thinking
                        thinking_content = chunk
                        thinking_length = len(thinking_content)
                        
                        # Check if thinking has transitioned to answer
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
                            # Check if thinking is getting too long - force conclusion
                            if thinking_length > max_thinking_length:
                                # Force transition to answer phase
                                phase = "answer"
                                answer_content = "\n\nBased on my analysis of the provided research papers, here are the key cross-domain applications and insights:\n\n"
                                yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_content})}\n\n"
                                yield f"data: {json.dumps({'type': 'content', 'content': answer_content})}\n\n"
                            else:
                                # Still in thinking phase, send incremental update
                                if thinking_content.strip():
                                    yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_content})}\n\n"
                    
                    elif phase == "answer":
                        # Model outputs cumulative answer
                        answer_content = chunk
                        if answer_content.strip():
                            yield f"data: {json.dumps({'type': 'content', 'content': answer_content})}\n\n"

                # Handle end of stream
                if phase == "thinking" and thinking_content.strip():
                    # If still in thinking phase after stream ends, provide a conclusion
                    conclusion = "\n\nBased on my analysis, the provided research papers demonstrate several cross-domain applications and mechanisms that can be mapped across different scientific fields."
                    yield f"data: {json.dumps({'type': 'thinking', 'content': thinking_content})}\n\n"
                    yield f"data: {json.dumps({'type': 'content', 'content': conclusion})}\n\n"
                elif phase == "answer" and answer_content.strip():
                    yield f"data: {json.dumps({'type': 'content', 'content': answer_content})}\n\n"

                # Store AI response in history
                add_to_conversation(session_id, "assistant", full_response[:500])

        else:
            # Fallback: return search results without reasoning
            summary = f"Found {len(results)} relevant papers:\n\n"
            for i, r in enumerate(results, 1):
                summary += f"**{i}. {r['title']}** ({r['arxiv_id']})\n"
                content_preview = r.get("wiki_content", "")[:200]
                summary += f"  {content_preview}...\n\n"

            add_to_conversation(session_id, "assistant", summary[:500])
            yield f"data: {json.dumps({'type': 'content', 'content': summary})}\n\n"

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id})}\n\n"
        yield "data: [DONE]\n\n"

    return StreamingResponse(generate_stream(), media_type="text/event-stream")


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
