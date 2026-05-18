from fastapi import Request

from server.services.chat_service import ChatService
from server.services.search_service import SearchService
from server.services.wiki_service import WikiService


def get_chat_service(request: Request) -> ChatService:
    # We can cache the instance in request.state if we want it per-request,
    # or just return a new instance or a singleton. 
    # For now, instantiating it is cheap enough.
    return ChatService()


def get_search_service(request: Request) -> SearchService:
    return SearchService()


def get_wiki_service(request: Request) -> WikiService:
    return WikiService()
