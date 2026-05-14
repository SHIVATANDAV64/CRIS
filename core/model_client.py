"""
Model Client — Unified interface for zira-researcher inference.
Supports both Modal.com (remote T4) and local GGUF fallback.
Uses OpenAI-compatible API for both modes.
"""
import re
from typing import Optional

from rich.console import Console

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
)
from config.prompts import CHAT_SYSTEM, CHAT_CONTEXT_TEMPLATE

console = Console()


class ModelClient:
    """
    Unified client for zira-researcher inference.

    Supports two modes:
    - Modal.com: Remote T4 GPU via OpenAI-compatible API (recommended)
    - Local: GGUF via llama-cpp-python (fallback for consumer GPUs)
    """

    def __init__(self, mode: Optional[str] = None):
        """
        Initialize the model client.

        Args:
            mode: 'modal', 'local', or None (auto-detect from config)
        """
        if mode is None:
            mode = "local" if USE_LOCAL_MODEL else "modal"

        self.mode = mode
        self._local_model = None
        self._remote_client = None

        if mode == "modal":
            self._init_modal()
        elif mode == "local":
            self._init_local()
        else:
            raise ValueError(f"Unknown mode: {mode}. Use 'modal' or 'local'.")

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
            api_key="not-needed",  # Modal uses its own auth
        )
        console.print("[green]Connected to Modal.com endpoint[/green]")

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

        console.print(f"[cyan]Loading local model: {model_path}...[/cyan]")
        self._local_model = Llama(
            model_path=model_path,
            n_gpu_layers=LOCAL_N_GPU_LAYERS,
            n_ctx=LOCAL_N_CTX,
            verbose=False,
        )
        console.print("[green]Local model loaded[/green]")

    def generate(
        self,
        user_message: str,
        wiki_context: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
    ) -> dict:
        """
        Generate a response using zira-researcher.

        Args:
            user_message: The user's research question
            wiki_context: List of wiki entry dicts to include as context
            system_prompt: Override the default system prompt

        Returns:
            Dict with 'response', 'thinking' (if available), 'tokens_used'
        """
        # Build the full prompt with wiki context
        sys_prompt = system_prompt or CHAT_SYSTEM

        if wiki_context:
            # Format wiki entries as numbered context
            entries_text = ""
            for i, entry in enumerate(wiki_context, 1):
                entries_text += f"\n### Entry {i}: {entry.get('title', 'Unknown')}\n"
                entries_text += f"**arXiv ID**: {entry.get('arxiv_id', '')}\n"
                entries_text += entry.get("wiki_content", "") + "\n"
                entries_text += "---\n"

            context_block = CHAT_CONTEXT_TEMPLATE.format(wiki_entries=entries_text)
            full_user_message = context_block + "\n\n" + user_message
        else:
            full_user_message = user_message

        if self.mode == "modal":
            return self._generate_modal(sys_prompt, full_user_message)
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
            console.print(f"[red]Modal inference error: {e}[/red]")
            return {
                "response": f"Error generating response: {str(e)}",
                "thinking": "",
                "tokens_used": 0,
                "mode": "modal",
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
            console.print(f"[red]Local inference error: {e}[/red]")
            return {
                "response": f"Error generating response: {str(e)}",
                "thinking": "",
                "tokens_used": 0,
                "mode": "local",
            }

    def _parse_thinking(self, content: str) -> tuple[str, str]:
        """
        Parse zira-researcher's <think>...</think> blocks.

        Returns:
            (thinking_text, answer_text) tuple
        """
        think_match = re.search(r'<think>(.*?)</think>', content, re.DOTALL)
        if think_match:
            thinking = think_match.group(1).strip()
            answer = content[think_match.end():].strip()
            return thinking, answer
        return "", content.strip()
