"""
Model Client — Unified interface for research reasoning inference.
Supports:
  - FINAL-Bench/Darwin-36B-Opus (base: Qwen/Qwen3.6-35B-A3B) via Modal.com
  - MiniMax M2.5 via AWS Bedrock (OpenAI-compatible endpoint)
"""
import re
import json
import requests
from typing import Optional, Generator

from config.settings import (
    MODAL_API_URL,
    REASONING_MODEL_ID,
    REASONING_MAX_TOKENS,
    REASONING_TEMPERATURE,
    REASONING_TOP_P,
    BEDROCK_BASE_URL,
    BEDROCK_MODEL,
    BEDROCK_API_KEY,
)
from config.prompts import CHAT_SYSTEM, CHAT_CONTEXT_TEMPLATE


class ModelClient:
    """
    Client for research reasoning inference.
    Supports Modal (Darwin-36B-Opus) and Bedrock (MiniMax M2.5) backends.
    """

    def __init__(self, model_id: Optional[str] = None):
        """
        Args:
            model_id: 'darwin-opus' (Modal) or 'minimax-m2.5' (Bedrock).
                      Defaults to 'darwin-opus' for backward compatibility.
        """
        self._model_id = model_id or "darwin-opus"

        if self._model_id == "minimax-m2.5":
            self._base_url = BEDROCK_BASE_URL.rstrip("/") + "/chat/completions"
            self._model_name = BEDROCK_MODEL
            self._use_bedrock = True
            print(f"[model_client] Using Bedrock ({self._model_name})")
        else:
            self._base_url = MODAL_API_URL.rstrip("/")
            self._model_name = REASONING_MODEL_ID
            self._use_bedrock = False
            print(f"[model_client] Connected to Modal ({self._model_name})")

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def model_name(self) -> str:
        return self._model_name

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

    def generate_stream(
        self,
        user_message: str,
        wiki_context: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        conversation_history: str = "",
    ) -> Generator[str, None, None]:
        """
        Generate a streaming response using the reasoning model.
        Yields chunks of text as they arrive from the model.
        """
        sys_prompt = system_prompt or CHAT_SYSTEM

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

        if conversation_history:
            full_user_message += conversation_history + "\n\n"

        full_user_message += user_message

        yield from self._generate_stream(sys_prompt, full_user_message)

    def _generate(self, system_prompt: str, user_message: str) -> dict:
        """Generate response via Modal or Bedrock endpoint."""
        try:
            payload = {
                "model": self._model_name if self._use_bedrock else None,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": REASONING_MAX_TOKENS,
                "temperature": REASONING_TEMPERATURE,
                "top_p": REASONING_TOP_P,
            }
            if not self._use_bedrock:
                payload.pop("model")

            headers = {"Content-Type": "application/json"}
            if self._use_bedrock and BEDROCK_API_KEY:
                headers["Authorization"] = f"Bearer {BEDROCK_API_KEY}"

            response = requests.post(
                self._base_url,
                json=payload,
                headers=headers,
                timeout=300,
            )
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"] or ""
            thinking, answer = self._parse_thinking(content)
            tokens = data.get("usage", {}).get("total_tokens", 0)

            mode_label = "bedrock" if self._use_bedrock else "modal"

            return {
                "response": answer,
                "thinking": thinking,
                "tokens_used": tokens,
                "mode": mode_label,
            }

        except Exception as e:
            provider = "Bedrock" if self._use_bedrock else "Modal"
            print(f"[model_client] {provider} inference error: {e}")
            return {
                "response": f"Error generating response: {str(e)}",
                "thinking": "",
                "tokens_used": 0,
                "mode": "modal" if not self._use_bedrock else "bedrock",
            }

    def _generate_stream(self, system_prompt: str, user_message: str) -> Generator[str, None, None]:
        """Generate streaming response via Modal or Bedrock endpoint using SSE.
        For Modal: collects full response, strips thinking, yields clean answer.
        For Bedrock: streams with real-time thinking tag filtering.
        """
        try:
            payload = {
                "model": self._model_name if self._use_bedrock else None,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": REASONING_MAX_TOKENS,
                "temperature": REASONING_TEMPERATURE,
                "top_p": REASONING_TOP_P,
                "stream": True,
            }
            if not self._use_bedrock:
                payload.pop("model")

            headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
            if self._use_bedrock and BEDROCK_API_KEY:
                headers["Authorization"] = f"Bearer {BEDROCK_API_KEY}"

            response = requests.post(
                self._base_url,
                json=payload,
                headers=headers,
                stream=True,
                timeout=300,
            )
            response.raise_for_status()

            content_type = response.headers.get("content-type", "")
            if "text/event-stream" not in content_type and "application/json" in content_type:
                data = response.json()
                content = data["choices"][0]["message"]["content"] or ""
                _, answer = self._parse_thinking(content)
                if answer:
                    yield answer
                return

            if not self._use_bedrock:
                # Modal: collect full response, strip thinking, yield clean answer
                full_content = ""
                for line in response.iter_lines():
                    if not line:
                        continue
                    line = line.decode("utf-8")
                    if line.startswith("data: "):
                        data_str = line[6:]
                        if data_str.strip() == "[DONE]":
                            break
                        try:
                            data = json.loads(data_str)
                            delta = data.get("choices", [{}])[0].get("delta", {})
                            chunk = delta.get("content", "")
                            if chunk:
                                full_content += chunk
                        except json.JSONDecodeError:
                            continue
                _, answer = self._parse_thinking(full_content)
                if answer:
                    yield answer
                return

            # Bedrock: stream with real-time thinking tag filtering
            in_thinking = False
            pending = ""

            for line in response.iter_lines():
                if not line:
                    continue
                line = line.decode("utf-8")
                if line.startswith("data: "):
                    data_str = line[6:]
                    if data_str.strip() == "[DONE]":
                        break
                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        chunk = delta.get("content", "")
                        if not chunk:
                            continue

                        pending += chunk

                        while pending:
                            if not in_thinking:
                                idx = pending.find("<think>")
                                if idx != -1:
                                    before = pending[:idx]
                                    if before:
                                        yield before
                                    pending = pending[idx + 9:]
                                    in_thinking = True
                                else:
                                    yield pending
                                    pending = ""
                            else:
                                idx = pending.find("</think>")
                                if idx != -1:
                                    pending = pending[idx + 10:]
                                    in_thinking = False
                                else:
                                    pending = ""
                                    break

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            provider = "Bedrock" if self._use_bedrock else "Modal"
            print(f"[model_client] {provider} streaming error: {e}")
            yield f"\n\n[Error: {str(e)}]"

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
