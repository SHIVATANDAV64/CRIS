import re
import uuid
import json
from typing import Optional, List, Dict, Any, AsyncGenerator
from urllib.parse import urlparse

from config.settings import CONTEXT_ENTRIES_LIMIT, WIKI_DIR, SEARXNG_MODAL_URL
from config.prompts import SEARCH_INTENT_ROUTER
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
from core.web_tools import get_search


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
        self._REALTIME_INDICATORS = [
            'latest', 'recent', 'today', 'yesterday', 'this week', 'this month',
            'this year', 'current', 'new', 'news', 'trending', 'update',
            '2024', '2025', '2026', 'now', 'right now', 'just', 'breaking',
            'search the web', 'look up online', 'find online', 'google',
            'what is happening', 'what happened',
        ]

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

    def needs_realtime_data(self, query: str) -> bool:
        """Keyword heuristic fallback: check if query needs real-time web data."""
        q_lower = query.lower().strip()
        for indicator in self._REALTIME_INDICATORS:
            if indicator in q_lower:
                return True
        return False

    def llm_route_search(self, query: str, model_id: Optional[str] = None, conversation_history: str = "") -> Dict[str, Any]:
        """
        Ask the LLM whether this query needs a web search (like ChatGPT/Perplexity).

        Returns:
            {"needs_search": bool, "queries": [str, ...], "reason": str}
        """
        try:
            client = self.get_model_client(model_id)
            if not client:
                return {"needs_search": False}

            context_section = ""
            if conversation_history:
                context_section = f"\nConversation context (last few messages):\n{conversation_history[-500:]}"

            prompt = SEARCH_INTENT_ROUTER.format(
                user_message=query,
                context_section=context_section,
            )

            result = client.generate(
                user_message=prompt,
                system_prompt="You are a search intent classifier. Return ONLY valid JSON.",
            )

            response_text = result.get("response", "").strip()
            # Extract JSON from the response (handle markdown code blocks)
            if "```" in response_text:
                json_match = re.search(r'```(?:json)?\s*(.+?)\s*```', response_text, re.DOTALL)
                if json_match:
                    response_text = json_match.group(1)
            # Also handle bare JSON
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)

            intent = json.loads(response_text)
            print(f"[search_router] LLM decision: needs_search={intent.get('needs_search')}, reason={intent.get('reason', 'N/A')}")
            return intent

        except Exception as e:
            print(f"[search_router] LLM routing failed ({e}), falling back to heuristic")
            # Fallback to keyword heuristic
            if self.needs_realtime_data(query):
                return {"needs_search": True, "queries": [query], "reason": "heuristic fallback"}
            return {"needs_search": False}

    def ensure_session(self, session_id: Optional[str], query: str) -> str:
        session_id = session_id or str(uuid.uuid4())
        if not get_session(session_id):
            title = query[:50] + ("..." if len(query) > 50 else "")
            create_session(session_id, title)
        return session_id

    async def fetch_sources(self, query: str, source_papers: Optional[List[str]], is_research: bool, model_id: Optional[str] = None) -> List[Dict[str, Any]]:
        results = []
        web_search_triggered = False
        search_queries = []

        # --- Step 1: Determine if web search is needed ---
        if SEARXNG_MODAL_URL:
            # Tier 1: keyword heuristic (instant)
            if self.needs_realtime_data(query):
                search_queries = [query]
                web_search_triggered = True
                print(f"[chat_service] Heuristic triggered web search for: {query}")

            # Tier 2: LLM router (if heuristic didn't trigger)
            if not search_queries:
                intent = self.llm_route_search(query, model_id)
                if intent.get("needs_search"):
                    search_queries = intent.get("queries", [query])
                    web_search_triggered = True
                    print(f"[chat_service] LLM triggered web search: {intent.get('reason', '')} -> {search_queries}")

        # --- Step 2: Fetch local papers (SKIP if web search is primary source) ---
        if source_papers:
            # User explicitly dropped papers — always include them
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
        elif is_research and not web_search_triggered:
            # Only fetch local papers if web search ISN'T the primary source
            # This prevents 15 random papers drowning out 5 relevant web results
            results = search(query, limit=CONTEXT_ENTRIES_LIMIT)

        # --- Step 3: Execute web searches ---
        if search_queries:
            try:
                web_search = get_search(SEARXNG_MODAL_URL)

                # Determine time_range for recency queries
                q_lower = query.lower()
                strong_recency = ['latest', 'today', 'this week', 'breaking', 'just', 'right now']
                mild_recency = ['recent', 'new', 'this month', 'this year', 'current', 'update']

                if any(w in q_lower for w in strong_recency):
                    time_range = "month"  # SearXNG "week" can be too restrictive; month with freshness scoring handles it
                elif any(w in q_lower for w in mild_recency):
                    time_range = "year"
                else:
                    time_range = None

                search_options = {"min_credibility": 0.40}  # Filter out low-quality sources
                if time_range:
                    search_options["time_range"] = time_range

                for sq in search_queries[:3]:  # Max 3 search queries
                    web_results = await web_search.search(sq, num_results=5, options=search_options if search_options else None)
                    for wr in web_results:
                        domain = urlparse(wr.get("url", "")).netloc.replace("www.", "")
                        # Build richer web content for the model to cite
                        snippet = wr.get("snippet", "")
                        web_url = wr.get("url", "")
                        pub_date = wr.get("published_date", "")
                        date_str = pub_date[:10] if pub_date else "Unknown date"

                        wiki_content = f"# {wr.get('title', '')}\n\n"
                        wiki_content += f"**Source**: [{domain}]({web_url})\n"
                        wiki_content += f"**Published**: {date_str}\n"
                        wiki_content += f"**Engine**: {wr.get('engine', 'web')}\n\n"
                        wiki_content += f"{snippet}"

                        results.append({
                            "arxiv_id": domain,
                            "title": wr.get("title", ""),
                            "contribution_type": "Web" if wr.get("category") != "news" else "News",
                            "domains": wr.get("category", "web"),
                            "categories": wr.get("engine", "web"),
                            "date_published": date_str,
                            "wiki_content": wiki_content,
                            "cross_domain_tags": "",
                            "relevance": wr.get("combined_score", 0),
                            "url": web_url,
                        })
            except Exception as e:
                print(f"[chat_service] Web search failed: {e}")

        return results

    def format_sources_for_response(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        sources = []
        for r in results:
            source = {
                "arxiv_id": r["arxiv_id"],
                "title": r["title"],
                "contribution_type": r.get("contribution_type", ""),
                "domains": r.get("domains", ""),
            }
            if r.get("url"):
                source["url"] = r["url"]
            sources.append(source)
        return sources

    async def process_chat(self, query: str, session_id: Optional[str], use_reasoning: bool, source_papers: Optional[List[str]], model_id: Optional[str]) -> Dict[str, Any]:
        session_id = self.ensure_session(session_id, query)
        add_message(session_id, "user", query)

        is_research = self.is_research_query(query)
        results = await self.fetch_sources(query, source_papers, is_research, model_id=model_id)
        sources = self.format_sources_for_response(results)

        if use_reasoning:
            client = self.get_model_client(model_id)
            if client:
                history_context = format_history_for_prompt(session_id)
                result = client.generate(
                    user_message=query,
                    wiki_context=results if (is_research or any(r.get('contribution_type') in ('Web', 'News') for r in results)) else None,
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

        # Emit "searching" event if we'll likely search the web
        will_search = self.needs_realtime_data(query)
        if will_search and SEARXNG_MODAL_URL:
            yield f"data: {json.dumps({'type': 'status', 'status': 'searching_web', 'message': 'Searching the web...'})}\n\n"

        results = await self.fetch_sources(query, source_papers, is_research, model_id=model_id)
        sources = self.format_sources_for_response(results)

        # Check if web results were found (for non-heuristic LLM-routed searches)
        web_types = ("Web", "News")
        has_web = any(r.get("contribution_type") in web_types for r in results)
        if has_web and not will_search:
            # LLM decided to search — notify the UI retroactively
            web_count = sum(1 for r in results if r.get("contribution_type") in web_types)
            yield f"data: {json.dumps({'type': 'status', 'status': 'web_results', 'message': f'Found {web_count} web results'})}\n\n"

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
                        wiki_context=results if (is_research or any(r.get('contribution_type') in ('Web', 'News') for r in results)) else None,
                        conversation_history=history_context,
                    ):
                        full_response += chunk
                        if chunk:
                            # Send token event for live streaming
                            yield f"data: {json.dumps({'type': 'token', 'token': chunk})}\n\n"
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
