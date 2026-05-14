"""
Modal.com Deployment — Serve zira-researcher on a T4 GPU via OpenAI-compatible API.

Deploy with:
    modal deploy modal_deploy/serve_model.py

This creates a serverless endpoint that:
- Spins up a T4 GPU on demand
- Loads zira-researcher with vLLM for fast inference
- Exposes an OpenAI-compatible /v1/chat/completions endpoint
- Shuts down after idle timeout (saves credits)
"""
import modal

# ── Modal App Setup ──────────────────────────────────────────────────────

app = modal.App("cris-zira-researcher")

# Container image with vLLM + model weights
vllm_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "vllm>=0.6.0",
        "transformers>=4.45.0",
        "torch>=2.4.0",
    )
)

MODEL_ID = "0xvoid0000/zira-researcher"
MODEL_REVISION = "main"


# ── vLLM Inference Server ────────────────────────────────────────────────

@app.cls(
    gpu="T4",  # $0.65/hour — fits well in free $30 credits
    image=vllm_image,
    scaledown_window=300,  # Shut down after 5 min idle (saves credits)
    timeout=600,  # 10 min max per request
    volumes={
        "/model-cache": modal.Volume.from_name("cris-model-cache", create_if_missing=True),
    },
)
class ZiraResearcher:
    @modal.enter()
    def load_model(self):
        """Load the model when the container starts."""
        from vllm import LLM, SamplingParams

        self.llm = LLM(
            model=MODEL_ID,
            revision=MODEL_REVISION,
            trust_remote_code=True,
            max_model_len=32768,  # 32K context — good balance of quality vs VRAM
            gpu_memory_utilization=0.90,
            download_dir="/model-cache",
            dtype="auto",
        )

        self.default_params = SamplingParams(
            temperature=1.0,
            top_p=0.95,
            top_k=20,
            max_tokens=8192,
            presence_penalty=1.5,
        )

    @modal.method()
    def generate(self, messages: list[dict], max_tokens: int = 8192, temperature: float = 1.0) -> dict:
        """Generate a response from zira-researcher."""
        from vllm import SamplingParams

        # Build the prompt from messages
        prompt = self._format_messages(messages)

        params = SamplingParams(
            temperature=temperature,
            top_p=0.95,
            top_k=20,
            max_tokens=max_tokens,
            presence_penalty=1.5,
        )

        outputs = self.llm.generate([prompt], params)
        result = outputs[0]
        text = result.outputs[0].text

        return {
            "content": text,
            "tokens_used": len(result.outputs[0].token_ids),
            "finish_reason": result.outputs[0].finish_reason,
        }

    def _format_messages(self, messages: list[dict]) -> str:
        """Format chat messages into the model's expected format."""
        from transformers import AutoTokenizer

        tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
        text = tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        return text

    @modal.fastapi_endpoint(method="POST", docs=True)
    def chat_completions(self, request: dict) -> dict:
        """
        OpenAI-compatible /v1/chat/completions endpoint.

        This makes it easy to switch between Modal and local inference —
        just change the base URL.
        """
        messages = request.get("messages", [])
        max_tokens = request.get("max_tokens", 8192)
        temperature = request.get("temperature", 1.0)

        result = self.generate.remote(messages, max_tokens, temperature)

        # Format as OpenAI-compatible response
        return {
            "id": "cris-" + str(hash(str(messages)))[:8],
            "object": "chat.completion",
            "model": MODEL_ID,
            "choices": [{
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": result["content"],
                },
                "finish_reason": result["finish_reason"],
            }],
            "usage": {
                "total_tokens": result["tokens_used"],
            },
        }


# ── Entrypoint for testing ──────────────────────────────────────────────

@app.local_entrypoint()
def test():
    """Quick test of the deployed model."""
    model = ZiraResearcher()
    result = model.generate.remote(
        messages=[
            {"role": "user", "content": "What are the key principles of cross-domain research synthesis?"}
        ],
        max_tokens=2048,
    )
    print(f"\nResponse:\n{result['content'][:500]}...")
    print(f"\nTokens used: {result['tokens_used']}")
