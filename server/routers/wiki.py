from fastapi import APIRouter, Depends, HTTPException

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
