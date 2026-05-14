"""
Model Client — Unified interface for research reasoning inference.
Supports three modes with automatic fallback:
  1. Modal.com (remote T4 GPU) — primary, best quality
  2. OpenRouter (Ring-2.6-1T, free) — fallback when Modal is unavailable
  3. Local GGUF — offline fallback for consumer GPUs
"""
import re
from typing import Optional

from config.settings import (
    MODAL_ENDPOINT_URL,
    REASONING_MODEL_ID,
    REASONING_MAX_TOKENS,
    REASONING_TEMPERATURE,
    REASONING_TOP_P,
    USE_LOCAL_MODEL,
    LOCAL_MODEL_PATH,
    LOCAL_N_GPU_LAYERS,
    LOCAL_N_CTX,
    OPENROUTER_API_KEY,
    OPENROUTER_BASE_URL,
    COMPILER_MODEL,
)
from config.prompts import CHAT_SYSTEM, CHAT_CONTEXT_TEMPLATE


class ModelClient:
    """
    Unified client for research reasoning inference.

    Fallback chain: Modal → OpenRouter → Local GGUF → Search-only
    """

    def __init__(self, mode: Optional[str] = None):
        """
        Initialize the model client.

        Args:
            mode: 'modal', 'openrouter', 'local', or None (auto-detect)
        """
        if mode is None:
            if USE_LOCAL_MODEL:
                mode = "local"
            elif MODAL_ENDPOINT_URL:
                mode = "modal"
            elif OPENROUTER_API_KEY:
                mode = "openrouter"
            else:
                mode = "openrouter"  # default

        self.mode = mode
        self._local_model = None
        self._remote_client = None
        self._openrouter_client = None

        if mode == "modal":
            self._init_modal()
        elif mode == "openrouter":
            self._init_openrouter()
        elif mode == "local":
            self._init_local()
        else:
            raise ValueError(f"Unknown mode: {mode}. Use 'modal', 'openrouter', or 'local'.")

    def _init_modal(self):
        """Initialize Modal.com remote client."""
        from openai import OpenAI

        if not MODAL_ENDPOINT_URL:
            raise ValueError(
                "MODAL_ENDPOINT_URL not set in .env. "
                "Deploy the model first with: modal deploy modal_deploy/serve_model.py"
            )

        self._remote_client = OpenAI(
            base_url=MODAL_ENDPOINT_URL,
            api_key="not-needed",
        )
        print("[model_client] Connected to Modal.com endpoint")

    def _init_openrouter(self):
        """Initialize OpenRouter client for reasoning fallback."""
        from openai import OpenAI

        if not OPENROUTER_API_KEY:
            raise ValueError("OPENROUTER_API_KEY not set in .env.")

        self._openrouter_client = OpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=OPENROUTER_API_KEY,
            default_headers={
                "HTTP-Referer": "https://github.com/cris-research",
                "X-Title": "CRIS - Cross-Domain Research Intelligence System",
            },
        )
        print(f"[model_client] Connected to OpenRouter ({COMPILER_MODEL})")

    def _init_local(self):
        """Initialize local GGUF model."""
        try:
            from llama_cpp import Llama
        except ImportError:
            raise ImportError(
                "llama-cpp-python not installed. Install with:\n"
                "pip install llama-cpp-python"
            )

        model_path = str(LOCAL_MODEL_PATH)
        if not LOCAL_MODEL_PATH.exists():
            raise FileNotFoundError(
                f"GGUF model not found at {model_path}. "
                "Download with: python scripts/setup_model.py"
            )

        print(f"[model_client] Loading local model: {model_path}...")
        self._local_model = Llama(
            model_path=model_path,
            n_gpu_layers=LOCAL_N_GPU_LAYERS,
            n_ctx=LOCAL_N_CTX,
            verbose=False,
        )
        print("[model_client] Local model loaded")

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

        # Try primary mode, fall back if it fails
        if self.mode == "modal":
            result = self._generate_modal(sys_prompt, full_user_message)
            if "Error" not in result["response"] or "error" not in result["response"].lower():
                return result
            # Modal failed — try OpenRouter fallback
            print("[model_client] Modal failed, falling back to OpenRouter...")
            if not self._openrouter_client:
                try:
                    self._init_openrouter()
                except Exception:
                    return result  # Return the Modal error if OpenRouter also fails
            return self._generate_openrouter(sys_prompt, full_user_message)

        elif self.mode == "openrouter":
            return self._generate_openrouter(sys_prompt, full_user_message)

        else:
            return self._generate_local(sys_prompt, full_user_message)

    def _generate_modal(self, system_prompt: str, user_message: str) -> dict:
        """Generate response via Modal.com endpoint."""
        try:
            response = self._remote_client.chat.completions.create(
                model=REASONING_MODEL_ID,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=REASONING_MAX_TOKENS,
                temperature=REASONING_TEMPERATURE,
                top_p=REASONING_TOP_P,
            )

            content = response.choices[0].message.content or ""
            thinking, answer = self._parse_thinking(content)

            return {
                "response": answer,
                "thinking": thinking,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
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

    def _generate_openrouter(self, system_prompt: str, user_message: str) -> dict:
        """Generate response via OpenRouter (free fallback)."""
        try:
            if not self._openrouter_client:
                self._init_openrouter()

            response = self._openrouter_client.chat.completions.create(
                model=COMPILER_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=REASONING_MAX_TOKENS,
                temperature=REASONING_TEMPERATURE,
            )

            content = response.choices[0].message.content or ""
            thinking, answer = self._parse_thinking(content)

            return {
                "response": answer,
                "thinking": thinking,
                "tokens_used": response.usage.total_tokens if response.usage else 0,
                "mode": "openrouter",
            }

        except Exception as e:
            print(f"[model_client] OpenRouter inference error: {e}")
            return {
                "response": f"Error generating response: {str(e)}",
                "thinking": "",
                "tokens_used": 0,
                "mode": "openrouter",
            }

    def _generate_local(self, system_prompt: str, user_message: str) -> dict:
        """Generate response via local GGUF model."""
        try:
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ]

            response = self._local_model.create_chat_completion(
                messages=messages,
                max_tokens=REASONING_MAX_TOKENS,
                temperature=REASONING_TEMPERATURE,
                top_p=REASONING_TOP_P,
                top_k=20,
            )

            content = response["choices"][0]["message"]["content"] or ""
            thinking, answer = self._parse_thinking(content)

            tokens = response.get("usage", {})

            return {
                "response": answer,
                "thinking": thinking,
                "tokens_used": tokens.get("total_tokens", 0),
                "mode": "local",
            }

        except Exception as e:
            print(f"[model_client] Local inference error: {e}")
            return {
                "response": f"Error generating response: {str(e)}",
                "thinking": "",
                "tokens_used": 0,
                "mode": "local",
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
