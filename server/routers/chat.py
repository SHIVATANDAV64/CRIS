import json
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from server.models.schemas import ChatRequest, ChatResponse
from server.services.chat_service import ChatService
from server.dependencies import get_chat_service

router = APIRouter(prefix="/api/chat", tags=["Chat"])


@router.post("", response_model=ChatResponse)
async def chat(
    req: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Standard synchronous chat endpoint.
    If use_reasoning is true, the reasoning model will be used.
    """
    if not req.message.strip():
        return ChatResponse(response="Please ask a research question.")

    result = await chat_service.process_chat(
        query=req.message,
        session_id=req.session_id,
        use_reasoning=req.use_reasoning,
        source_papers=req.source_papers,
        model_id=req.model_id
    )
    return ChatResponse(**result)


@router.post("/stream")
async def chat_stream(
    req: ChatRequest,
    chat_service: ChatService = Depends(get_chat_service)
):
    """
    Streaming chat endpoint via Server-Sent Events (SSE).
    """
    if not req.message.strip():
        async def error_stream():
            yield f"data: {json.dumps({'type': 'error', 'content': 'Please ask a research question.'})}\n\n"
            yield "data: [DONE]\n\n"
        return StreamingResponse(error_stream(), media_type="text/event-stream")

    return StreamingResponse(
        chat_service.process_chat_stream(
            query=req.message,
            session_id=req.session_id,
            use_reasoning=req.use_reasoning,
            source_papers=req.source_papers,
            model_id=req.model_id
        ),
        media_type="text/event-stream"
    )
