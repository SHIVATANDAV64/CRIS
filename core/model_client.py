"""
Model Client — Unified interface for research reasoning inference.
Supports two modes with automatic fallback:
  1. Amazon Bedrock (MiniMax M2.5) — primary, cloud inference
  2. Local GGUF — offline fallback for consumer GPUs
"""
import re
from typing import Optional

from config.settings import (
    BEDROCK_API_KEY,
    BEDROCK_BASE_URL,
    REASONING_MODEL_ID,
    REASONING_MAX_TOKENS,
    REASONING_TEMPERATURE,
    REASONING_TOP_P,
    USE_LOCAL_MODEL,
    LOCAL_MODEL_PATH,
    LOCAL_N_GPU_LAYERS,
    LOCAL_N_CTX,
)
from config.prompts import CHAT_SYSTEM, CHAT_CONTEXT_TEMPLATE


class ModelClient:
    """
    Unified client for research reasoning inference.

    Fallback chain: Amazon Bedrock → Local GGUF → Search-only
    """

    def __init__(self, mode: Optional[str] = None):
        """
        Initialize the model client.

        Args:
            mode: 'bedrock', 'local', or None (auto-detect)
        """
        if mode is None:
            if USE_LOCAL_MODEL:
                mode = "local"
            elif BEDROCK_API_KEY:
                mode = "bedrock"
            else:
                mode = "bedrock"  # default — will error with helpful message

        self.mode = mode
        self._local_model = None
        self._bedrock_client = None

        if mode == "bedrock":
            self._init_bedrock()
        elif mode == "local":
            self._init_local()
        else:
            raise ValueError(f"Unknown mode: {mode}. Use 'bedrock' or 'local'.")

    def _init_bedrock(self):
        """Initialize Amazon Bedrock client via OpenAI-compatible endpoint."""
        from openai import OpenAI

        if not BEDROCK_API_KEY:
            raise ValueError(
                "BEDROCK_API_KEY not set in .env.\n"
                "Get a long-term API key from: https://console.aws.amazon.com/bedrock/"
            )

        self._bedrock_client = OpenAI(
            base_url=BEDROCK_BASE_URL,
            api_key=BEDROCK_API_KEY,
        )
        print(f"[model_client] Connected to Amazon Bedrock ({REASONING_MODEL_ID})")

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
        if self.mode == "bedrock":
            result = self._generate_bedrock(sys_prompt, full_user_message)
            if not result.get("_error"):
                return result
            # Bedrock failed — try local fallback if available
            print("[model_client] Bedrock failed, checking for local fallback...")
            if self._local_model:
                return self._generate_local(sys_prompt, full_user_message)
            return result
        else:
            return self._generate_local(sys_prompt, full_user_message)

    def _generate_bedrock(self, system_prompt: str, user_message: str) -> dict:
        """Generate response via Amazon Bedrock (streaming)."""
        try:
            # Use streaming since Bedrock has streaming enabled
            stream = self._bedrock_client.chat.completions.create(
                model=REASONING_MODEL_ID,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_message},
                ],
                max_tokens=REASONING_MAX_TOKENS,
                temperature=REASONING_TEMPERATURE,
                top_p=REASONING_TOP_P,
                stream=True,
            )

            # Collect streamed chunks into full response
            content_parts = []
            for chunk in stream:
                if chunk.choices and chunk.choices[0].delta.content:
                    content_parts.append(chunk.choices[0].delta.content)

            content = "".join(content_parts)
            thinking, answer = self._parse_thinking(content)

            return {
                "response": answer,
                "thinking": thinking,
                "tokens_used": 0,  # Token count not available in streaming mode
                "mode": "bedrock",
            }

        except Exception as e:
            print(f"[model_client] Bedrock inference error: {e}")
            return {
                "response": f"Error generating response: {str(e)}",
                "thinking": "",
                "tokens_used": 0,
                "mode": "bedrock",
                "_error": True,
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

