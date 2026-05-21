from fastapi import APIRouter, Depends, HTTPException
import json
from pathlib import Path

from server.models.schemas import ChatRequest
from server.services.wiki_service import WikiService
from server.services.chat_service import ChatService
from server.dependencies import get_wiki_service, get_chat_service
from core.chat_store import get_messages
from config.settings import WIKI_DIR
from core.chat_memory import extract_and_store_memory

router = APIRouter(tags=["Wiki & Memory"])


@router.post("/api/memory/extract")
async def extract_memory(
    req: ChatRequest,
    wiki_service: WikiService = Depends(get_wiki_service)
):
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


@router.get("/api/wiki/stats")
async def wiki_stats(wiki_service: WikiService = Depends(get_wiki_service)):
    """Get wiki knowledge base statistics."""
    return wiki_service.get_stats()


@router.post("/api/wiki/rebuild")
async def wiki_rebuild(wiki_service: WikiService = Depends(get_wiki_service)):
    """Rebuild wiki structure (summaries, graph, etc.)."""
    wiki_service.rebuild_all()
    return {"status": "success"}


@router.get("/api/wiki/entities")
async def wiki_entities(wiki_service: WikiService = Depends(get_wiki_service)):
    """List all extracted entities."""
    entities = wiki_service.get_entities()
    return {"count": len(entities), "entities": entities}


@router.get("/api/wiki/notes")
async def wiki_notes(wiki_service: WikiService = Depends(get_wiki_service)):
    """List all conversation notes."""
    notes = wiki_service.get_notes()
    return {"count": len(notes), "notes": notes}


@router.get("/api/wiki/graph")
async def wiki_graph(wiki_service: WikiService = Depends(get_wiki_service)):
    """Get the wiki force-directed graph data."""
    graph_path = Path(wiki_service.wiki_dir) / "graph.json"
    if not graph_path.exists():
        try:
            wiki_service.rebuild_all()
        except Exception as e:
            print(f"Error rebuilding wiki for graph: {e}")
            
    if graph_path.exists():
        try:
            with open(graph_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Failed to read graph: {e}")
            
    return {"nodes": [], "edges": []}


@router.get("/api/wiki/detail/{node_type}/{node_id}")
async def wiki_detail(
    node_type: str,
    node_id: str,
    wiki_service: WikiService = Depends(get_wiki_service)
):
    """Get detail content of a wiki node."""
    mgr = wiki_service.wiki_manager
    if node_type == "paper":
        folder = mgr.sources_dir
    elif node_type == "concept":
        folder = mgr.concepts_dir
    elif node_type == "entity":
        folder = mgr.entities_dir
    elif node_type == "note":
        folder = mgr.notes_dir
    else:
        raise HTTPException(status_code=400, detail=f"Invalid node type: {node_type}")

    # Slashes are replaced with underscores in filenames for papers (e.g. 2404.12345)
    safe_id = node_id.replace("/", "_")
    file_path = folder / f"{safe_id}.md"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Wiki entry not found: {node_id} (tried {file_path})")

    try:
        content = file_path.read_text(encoding="utf-8")
        fm, body = mgr.parse_frontmatter(content)
        return {
            "id": node_id,
            "type": node_type,
            "metadata": fm,
            "content": body
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read wiki entry: {e}")

