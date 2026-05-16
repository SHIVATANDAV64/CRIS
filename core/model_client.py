"""
Model Client — Unified interface for research reasoning inference.
Uses zira-researcher deployed on Modal.com via OpenAI-compatible endpoint.
"""
import re
import requests
from typing import Optional

from config.settings import (
    MODAL_API_URL,
    REASONING_MODEL_ID,
    REASONING_MAX_TOKENS,
    REASONING_TEMPERATURE,
    REASONING_TOP_P,
)
from config.prompts import CHAT_SYSTEM, CHAT_CONTEXT_TEMPLATE


class ModelClient:
    """
    Client for research reasoning inference via Modal.com (zira-researcher).
    """

    def __init__(self):
        self._base_url = MODAL_API_URL.rstrip("/")
        print(f"[model_client] Connected to Modal ({REASONING_MODEL_ID})")

    def generate(
        self,
        user_message: str,
        wiki_context: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        conversation_history: str = "",
    ) -> dict:
        """
        Generate a response using the reasoning model.

        Args:
            user_message: The user's research question
            wiki_context: List of wiki entry dicts to include as context
            system_prompt: Override the default system prompt
            conversation_history: Formatted conversation history string

        Returns:
            Dict with 'response', 'thinking' (if available), 'tokens_used', 'mode'
        """
        sys_prompt = system_prompt or CHAT_SYSTEM

        # Build the full prompt with wiki context + conversation history
        full_user_message = ""

        if wiki_context:
            entries_text = ""
            for i, entry in enumerate(wiki_context, 1):
                entries_text += f"\n### Entry {i}: {entry.get('title', 'Unknown')}\n"
                entries_text += f"**arXiv ID**: {entry.get('arxiv_id', '')}\n"
                entries_text += entry.get("wiki_content", "") + "\n"
                entries_text += "---\n"

            context_block = CHAT_CONTEXT_TEMPLATE.format(wiki_entries=entries_text)
            full_user_message = context_block + "\n\n"

        # Add conversation history if available
        if conversation_history:
            full_user_message += conversation_history + "\n\n"

        full_user_message += user_message

        return self._generate(sys_prompt, full_user_message)

    def _generate(self, system_prompt: str, user_message: str) -> dict:
        """Generate response via Modal endpoint."""
        try:
            payload = {
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": REASONING_MAX_TOKENS,
                "temperature": REASONING_TEMPERATURE,
            }

            response = requests.post(
                self._base_url,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"] or ""
            thinking, answer = self._parse_thinking(content)
            tokens = data.get("usage", {}).get("total_tokens", 0)

            return {
                "response": answer,
                "thinking": thinking,
                "tokens_used": tokens,
                "mode": "modal",
            }

        except Exception as e:
            print(f"[model_client] Modal inference error: {e}")
            return {
                "response": f"Error generating response: {str(e)}",
                "thinking": "",
                "tokens_used": 0,
                "mode": "modal",
            }

    def _parse_thinking(self, content: str) -> tuple[str, str]:
        """
        Parse <think>...</think> blocks from reasoning models.

        Returns:
            (thinking_text, answer_text) tuple
        """
        think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
        if think_match:
            thinking = think_match.group(1).strip()
            answer = content[think_match.end():].strip()
            return thinking, answer
        return "", content.strip()
