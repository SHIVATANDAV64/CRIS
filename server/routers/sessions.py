import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from fastapi.responses import JSONResponse

from core.chat_store import (
    create_session,
    get_session,
    update_session_title,
    delete_session,
    list_sessions,
    get_messages,
)
from server.models.schemas import SessionCreate, SessionTitleUpdate

router = APIRouter(prefix="/api/sessions", tags=["Sessions"])


@router.get("")
async def get_all_sessions(limit: int = 50, offset: int = 0):
    """List all chat sessions."""
    sessions = list_sessions(limit=limit, offset=offset)
    return {"count": len(sessions), "sessions": sessions}


@router.post("")
async def create_new_session(req: SessionCreate):
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    session = create_session(session_id, req.title or "New Chat")
    return session


@router.get("/{session_id}")
async def get_session_messages(session_id: str):
    """Get all messages for a session."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    messages = get_messages(session_id)
    return {"session": session, "messages": messages}


@router.get("/{session_id}/export")
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


@router.patch("/{session_id}")
async def update_session(session_id: str, req: SessionTitleUpdate):
    """Update a session's title."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    update_session_title(session_id, req.title)
    return {"id": session_id, "title": req.title}


@router.delete("/{session_id}")
async def delete_session_endpoint(session_id: str):
    """Delete a session and all its messages."""
    session = get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    delete_session(session_id)
    return {"deleted": session_id}
