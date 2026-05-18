import re
import uuid
import json
from typing import Optional, List, Dict, Any, AsyncGenerator

from config.settings import CONTEXT_ENTRIES_LIMIT, WIKI_DIR
from core.search_engine import search
from core.domain_manager import get_paper_by_id
from core.chat_store import (
    get_session,
    create_session,
    add_message,
    format_history_for_prompt,
)
from core.chat_memory import extract_and_store_memory
from core.model_client import ModelClient


class ChatService:
    def __init__(self):
        self._NON_RESEARCH_PATTERNS = [
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
        self._RESEARCH_INDICATORS = [
            'paper', 'research', 'study', 'method', 'algorithm', 'model', 'neural',
            'network', 'learning', 'domain', 'cross-domain', 'transfer', 'mechanism',
            'compare', 'difference', 'similar', 'connection', 'relation', 'analysis',
            'explain', 'how does', 'what is', 'why', 'summarize', 'review',
            'arxiv', 'citation', 'experiment', 'dataset', 'performance', 'accuracy',
            'technique', 'approach', 'framework', 'system', 'architecture',
        ]
        self._model_clients: dict[str, ModelClient] = {}

    def get_model_client(self, model_id: Optional[str] = None) -> ModelClient:
        key = model_id or "darwin-opus"
        if key not in self._model_clients:
            try:
                self._model_clients[key] = ModelClient(model_id=model_id)
            except Exception as e:
                print(f"Warning: Could not initialize model client ({key}): {e}")
        return self._model_clients.get(key)

    def is_research_query(self, query: str) -> bool:
        q_lower = query.lower().strip()
        for pattern in self._NON_RESEARCH_PATTERNS:
            if re.match(pattern, q_lower):
                return False
        if len(q_lower.split()) <= 3:
            return False
        for indicator in self._RESEARCH_INDICATORS:
            if indicator in q_lower:
                return True
        return len(q_lower.split()) >= 5

    def ensure_session(self, session_id: Optional[str], query: str) -> str:
        session_id = session_id or str(uuid.uuid4())
        if not get_session(session_id):
            title = query[:50] + ("..." if len(query) > 50 else "")
            create_session(session_id, title)
        return session_id

    def fetch_sources(self, query: str, source_papers: Optional[List[str]], is_research: bool) -> List[Dict[str, Any]]:
        results = []
        if source_papers:
            for arxiv_id in source_papers:
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
            
        return results

    def format_sources_for_response(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "arxiv_id": r["arxiv_id"],
                "title": r["title"],
                "contribution_type": r.get("contribution_type", ""),
                "domains": r.get("domains", ""),
            }
            for r in results
        ]

    def process_chat(self, query: str, session_id: Optional[str], use_reasoning: bool, source_papers: Optional[List[str]], model_id: Optional[str]) -> Dict[str, Any]:
        session_id = self.ensure_session(session_id, query)
        add_message(session_id, "user", query)

        is_research = self.is_research_query(query)
        results = self.fetch_sources(query, source_papers, is_research)
        sources = self.format_sources_for_response(results)

        if use_reasoning:
            client = self.get_model_client(model_id)
            if client:
                history_context = format_history_for_prompt(session_id)
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

                return {
                    "response": result["response"],
                    "thinking": result.get("thinking", ""),
                    "sources": sources,
                    "tokens_used": result.get("tokens_used", 0),
                    "mode": result.get("mode", ""),
                    "session_id": session_id,
                }

        summary = f"Found {len(results)} relevant papers:\n\n"
        for i, r in enumerate(results, 1):
            summary += f"**{i}. {r['title']}** ({r['arxiv_id']})\n"
            content_preview = r.get("wiki_content", "")[:200]
            summary += f"  {content_preview}...\n\n"

        add_message(session_id, "assistant", summary)

        return {
            "response": summary,
            "thinking": "",
            "sources": sources,
            "tokens_used": 0,
            "mode": "search-only",
            "session_id": session_id,
        }

    async def process_chat_stream(self, query: str, session_id: Optional[str], use_reasoning: bool, source_papers: Optional[List[str]], model_id: Optional[str]) -> AsyncGenerator[str, None]:
        session_id = self.ensure_session(session_id, query)
        add_message(session_id, "user", query)

        is_research = self.is_research_query(query)
        results = self.fetch_sources(query, source_papers, is_research)
        sources = self.format_sources_for_response(results)

        if sources:
            yield f"data: {json.dumps({'type': 'sources', 'sources': sources, 'session_id': session_id})}\n\n"

        if use_reasoning:
            client = self.get_model_client(model_id)
            if client:
                history_context = format_history_for_prompt(session_id)
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
                        full_response if full_response else f"Error: {str(e) if 'e' in locals() else 'Stream failed'}",
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
