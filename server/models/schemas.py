from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any


class ChatRequest(BaseModel):
    message: str = Field(..., description="The user's input message or research question.")
    session_id: Optional[str] = Field(None, description="The ID of the existing chat session. A new one will be created if omitted.")
    use_reasoning: bool = Field(True, description="Whether to use the reasoning LLM (True) or just perform a search (False).")
    source_papers: Optional[List[str]] = Field(None, description="List of arXiv IDs of papers to strictly use as context.")
    model_id: Optional[str] = Field(None, description="The model ID to use (e.g., 'darwin-opus' or 'minimax-m2.5').")
    web_search: Optional[bool] = Field(None, description="Force enable/disable Web Search (True to force web search, False to disable, None to auto-route).")

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Explain the concept of quantum entanglement.",
                "use_reasoning": True
            }
        }


class ChatResponse(BaseModel):
    response: str = Field(..., description="The assistant's text response.")
    thinking: str = Field("", description="The reasoning trace if the model supports it.")
    sources: List[Dict[str, Any]] = Field(default_factory=list, description="List of sources cited in the response.")
    tokens_used: int = Field(0, description="Number of tokens used in generation.")
    mode: str = Field("", description="The mode in which the response was generated (e.g., search-only).")
    session_id: str = Field("", description="The ID of the chat session.")


class SettingsUpdate(BaseModel):
    updates: Dict[str, Any] = Field(..., description="A dictionary of nested settings to update.")

    class Config:
        json_schema_extra = {
            "example": {
                "updates": {
                    "chat": {
                        "streaming_enabled": False
                    }
                }
            }
        }


class SessionCreate(BaseModel):
    title: Optional[str] = Field("New Chat", description="The title of the new session.")


class SessionTitleUpdate(BaseModel):
    title: str = Field(..., description="The new title for the session.")


class WebSearchRequest(BaseModel):
    query: str = Field(..., description="The search query.")
    num_results: int = Field(5, description="Number of results to return.")
    time_range: Optional[str] = Field(None, description="Filter by time range: 'day', 'week', 'month', 'year'.")
    categories: Optional[List[str]] = Field(None, description="Categories like 'general', 'academic', 'news'.")
    engines: Optional[List[str]] = Field(None, description="Specific engines like 'duckduckgo', 'arxiv', 'wikipedia'.")
    min_credibility: float = Field(0.0, description="Minimum credibility score (0.0 to 1.0).")

    class Config:
        json_schema_extra = {
            "example": {
                "query": "recent advancements in fusion energy",
                "num_results": 5,
                "categories": ["academic", "news"]
            }
        }


class WebScrapeRequest(BaseModel):
    url: str = Field(..., description="The URL of the webpage to scrape.")
