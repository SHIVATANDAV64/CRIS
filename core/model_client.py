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

from config.settings import get_config
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

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def _use_bedrock(self) -> bool:
        return self._model_id == "minimax-m2.5"

    @property
    def _base_url(self) -> str:
        config = get_config()
        if self._use_bedrock:
            bedrock_config = config.get("bedrock", {})
            base = bedrock_config.get("base_url", "").rstrip("/")
            # Auto-detect if it's bedrock-runtime or bedrock-mantle
            if "bedrock-runtime" in base:
                if not base.endswith("/openai/v1"):
                    base = base + "/openai/v1"
            if not base.endswith("/chat/completions"):
                return base + "/chat/completions"
            return base
        else:
            model_config = config.get("model", {})
            return model_config.get("modal_api_url", "").rstrip("/")

    @property
    def _model_name(self) -> str:
        config = get_config()
        if self._use_bedrock:
            return config.get("bedrock", {}).get("model", "minimax.minimax-m2.5")
        else:
            return config.get("model", {}).get("modal_model", "")

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
                ctype = entry.get("contribution_type", "")
                if ctype in ("Web", "News"):
                    # Web source — clearly label as web content
                    entries_text += f"\n### [WEB SOURCE {i}]: {entry.get('title', 'Unknown')}\n"
                    entries_text += f"**URL**: {entry.get('url', entry.get('arxiv_id', ''))}\n"
                    entries_text += f"**Type**: {ctype}\n"
                else:
                    # Research paper
                    entries_text += f"\n### [PAPER {i}]: {entry.get('title', 'Unknown')}\n"
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
    ) -> Generator[tuple[str, str], None, None]:
        """
        Generate a streaming response using the reasoning model.
        Yields (token_type, chunk) as they arrive from the model.
        """
        sys_prompt = system_prompt or CHAT_SYSTEM

        full_user_message = ""

        if wiki_context:
            entries_text = ""
            for i, entry in enumerate(wiki_context, 1):
                ctype = entry.get("contribution_type", "")
                if ctype in ("Web", "News"):
                    entries_text += f"\n### [WEB SOURCE {i}]: {entry.get('title', 'Unknown')}\n"
                    entries_text += f"**URL**: {entry.get('url', entry.get('arxiv_id', ''))}\n"
                    entries_text += f"**Type**: {ctype}\n"
                else:
                    entries_text += f"\n### [PAPER {i}]: {entry.get('title', 'Unknown')}\n"
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
            config = get_config()
            model_config = config.get("model", {})
            bedrock_config = config.get("bedrock", {})
            api_key = bedrock_config.get("api_key", "")

            payload = {
                "model": self._model_name if self._use_bedrock else None,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": model_config.get("max_tokens", 32768),
                "temperature": model_config.get("temperature", 0.7),
                "top_p": model_config.get("top_p", 0.95),
            }
            if not self._use_bedrock:
                payload.pop("model")

            headers = {"Content-Type": "application/json"}
            if self._use_bedrock and api_key:
                headers["Authorization"] = f"Bearer {api_key}"

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
                "mode": "bedrock" if self._use_bedrock else "modal",
            }

    def _generate_stream(self, system_prompt: str, user_message: str) -> Generator[tuple[str, str], None, None]:
        """
        Generate streaming response via Modal or Bedrock endpoint using SSE.
        Yields (token_type, chunk) IMMEDIATELY as they arrive for true live streaming.
        """
        try:
            config = get_config()
            model_config = config.get("model", {})
            bedrock_config = config.get("bedrock", {})
            api_key = bedrock_config.get("api_key", "")

            payload = {
                "model": self._model_name if self._use_bedrock else None,
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                "max_tokens": model_config.get("max_tokens", 32768),
                "temperature": model_config.get("temperature", 0.7),
                "top_p": model_config.get("top_p", 0.95),
                "stream": True,
            }
            if not self._use_bedrock:
                payload.pop("model")

            headers = {"Content-Type": "application/json", "Accept": "text/event-stream"}
            if self._use_bedrock and api_key:
                headers["Authorization"] = f"Bearer {api_key}"

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
                thinking, answer = self._parse_thinking(content)
                if thinking:
                    yield "thinking", thinking
                if answer:
                    yield "content", answer
                return

            # Streaming mode: yield tokens IMMEDIATELY as they arrive
            in_thinking = False
            saw_answer = False

            for line in response.iter_lines():
                if not line:
                    continue

                line_str = line.decode("utf-8").strip()

                if line_str.startswith("data:"):
                    data_str = line_str[5:].strip()

                    if data_str == "[DONE]":
                        break

                    try:
                        data = json.loads(data_str)
                        delta = data.get("choices", [{}])[0].get("delta", {})
                        
                        # Support direct reasoning_content (e.g. Bedrock/DeepSeek)
                        reasoning_chunk = delta.get("reasoning_content", "")
                        if reasoning_chunk:
                            yield "thinking", reasoning_chunk
                            continue

                        chunk = delta.get("content", "")
                        if not chunk:
                            continue

                        # Handle thinking tags in real-time
                        if "   <think>  " in chunk or "<think>" in chunk:
                            in_thinking = True
                            tag = "   <think>  " if "   <think>  " in chunk else "<think>"
                            parts = chunk.split(tag, 1)
                            if parts[0] and not saw_answer:
                                clean_token = self._strip_tool_calls(parts[0])
                                if clean_token:
                                    saw_answer = True
                                    yield "content", clean_token
                            if parts[1]:
                                yield "thinking", parts[1]
                            continue

                        if "剱" in chunk or "</think>" in chunk:
                            in_thinking = False
                            tag = "剱" if "剱" in chunk else "</think>"
                            parts = chunk.split(tag, 1)
                            if parts[0]:
                                yield "thinking", parts[0]
                            if len(parts) > 1 and parts[1]:
                                if not saw_answer:
                                    clean_token = self._clean_opening(parts[1])
                                    clean_token = self._strip_tool_calls(clean_token)
                                else:
                                    clean_token = self._strip_tool_calls(parts[1])
                                if clean_token:
                                    saw_answer = True
                                    yield "content", clean_token
                            continue

                        if in_thinking:
                            yield "thinking", chunk
                        else:
                            # Regular token: clean and yield immediately
                            if not saw_answer:
                                clean_token = self._clean_opening(chunk)
                                clean_token = self._strip_tool_calls(clean_token)
                                saw_answer = True
                            else:
                                clean_token = self._strip_tool_calls(chunk)

                            if clean_token:
                                yield "content", clean_token

                    except json.JSONDecodeError:
                        continue

        except Exception as e:
            provider = "Bedrock" if self._use_bedrock else "Modal"
            print(f"[model_client] {provider} streaming error: {e}")
            yield "content", f"\n\n[Error: {str(e)}]"

    def _parse_thinking(self, content: str) -> tuple[str, str]:
        """
        Parse <think>...</think> blocks from reasoning models.

        Returns:
            (thinking_text, answer_text) tuple
        """
        # First strip any tool call XML
        content = self._strip_tool_calls(content)

        # Case 1: Both <think> and </think> present (standard reasoning model output)
        think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
        if think_match:
            thinking = think_match.group(1).strip()
            answer = content[think_match.end():].strip()
            return thinking, self._clean_opening(answer)

        # Case 2: Only </think> present (model outputs thinking without opening tag)
        close_idx = content.find('</think>')
        if close_idx != -1:
            thinking = content[:close_idx].strip()
            answer = content[close_idx + len('</think>'):].strip()
            print(f"[model_client] Stripped orphan </think> tag ({len(thinking)} chars of thinking)")
            return thinking, self._clean_opening(answer)

        return "", self._clean_opening(content.strip())

    def _clean_opening(self, text: str) -> str:
        """
        Strip 'Based on...' opening sentences that models stubbornly produce.

        Checks the first 5 non-empty lines (models hide it after the heading).
        """
        if not text:
            return text

        prohibited_starts = [
            'based on ', 'according to the ', 'from the context',
            'the sources indicate', 'looking at the sources',
            'reviewing the provided', 'from the provided',
            'based upon ', 'drawing from ', 'from the research context',
            'the provided research', 'from the provided research',
        ]

        lines = text.split('\n')
        cleaned_lines = []
        checks_remaining = 5  # Only check first 5 non-empty lines

        for line in lines:
            stripped = line.strip().lower()

            if not stripped:
                cleaned_lines.append(line)
                continue

            if checks_remaining > 0:
                checks_remaining -= 1
                if any(stripped.startswith(p) for p in prohibited_starts):
                    print(f"[model_client] Stripped 'Based on...' line: {line.strip()[:60]}...")
                    continue  # Skip this line

            cleaned_lines.append(line)

        return '\n'.join(cleaned_lines).strip()

    def _strip_tool_calls(self, content: str) -> str:
        """
        Strip tool call XML from model responses.

        Some models (MiniMax M2.5) have native tool calling and may emit
        <minimax:tool_call>, <tool_call>, or similar XML instead of answering.
        This strips those blocks and returns clean text.
        """
        if not content:
            return content

        # Strip common tool call patterns
        patterns = [
            r'<minimax:tool_call>.*?</minimax:tool_call>',
            r'<tool_call>.*?</tool_call>',
            r'<function_call>.*?</function_call>',
            r'<invoke\s+name="[^"]*">.*?</invoke>',
        ]

        cleaned = content
        for pattern in patterns:
            cleaned = re.sub(pattern, '', cleaned, flags=re.DOTALL)

        # Also strip self-closing / unclosed tool call tags
        cleaned = re.sub(r'<minimax:tool_call\s*/?\s*>', '', cleaned)
        cleaned = re.sub(r'</?minimax:[^>]*>', '', cleaned)

        cleaned = cleaned.strip()

        # If stripping left nothing, the model only output a tool call
        if not cleaned and content.strip():
            print(f"[model_client] WARNING: Model output was entirely a tool call, returning fallback")
            return "I have the information from web search results provided in my context. Let me analyze it and provide a response.\n\n*Note: The model attempted to use an external tool instead of using the provided context. Please try again.*"

        return cleaned
