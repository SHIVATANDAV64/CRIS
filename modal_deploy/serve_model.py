"""
Modal.com Deployment — Serve zira-researcher via OpenAI-compatible API with streaming.

Deploy with:
    modal deploy modal_deploy/serve_model.py

After deploy, the endpoint is available at:
    https://cris-zira-researcher--chat-completions.modal.run
"""
import modal
import json
import time
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
from fastapi.responses import StreamingResponse

app = modal.App("cris-zira-researcher")

# Use a lightweight image - just transformers + torch + fastapi
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.4.0",
        "transformers>=4.45.0",
        "accelerate>=0.30.0",
        "fastapi>=0.115.0",
    )
)

MODEL_ID = "0xvoid0000/zira-researcher"


class ChatRequest(BaseModel):
    messages: list[dict]
    max_tokens: int = 4096
    temperature: float = 0.7
    stream: bool = False


class ChatResponse(BaseModel):
    id: str
    object: str
    model: str
    choices: list[dict]
    usage: dict


@app.cls(
    gpu="T4",
    image=image,
    scaledown_window=300,
    timeout=600,
    volumes={
        "/model-cache": modal.Volume.from_name("cris-model-cache", create_if_missing=True),
    },
)
class ZiraResearcher:
    @modal.enter()
    def load_model(self):
        """Load the model when the container starts."""
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            cache_dir="/model-cache",
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            torch_dtype=torch.float16,
            device_map="auto",
            cache_dir="/model-cache",
        )

    @modal.method()
    def generate(self, messages: list[dict], max_tokens: int = 4096, temperature: float = 0.7) -> dict:
        """Generate a response from zira-researcher."""
        import torch

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=0.95,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        # Decode only the generated part
        generated_tokens = outputs[0][inputs["input_ids"].shape[1]:]
        text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)

        return {
            "content": text,
            "tokens_used": len(generated_tokens),
        }

    @modal.method()
    def generate_stream(self, messages: list[dict], max_tokens: int = 4096, temperature: float = 0.7):
        """Generate response token-by-token for streaming."""
        import torch

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=0.95,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        # Yield tokens progressively
        full_text = ""
        for i in range(inputs["input_ids"].shape[1], len(outputs[0])):
            token = self.tokenizer.decode(outputs[0][i], skip_special_tokens=True)
            full_text += token
            yield full_text

    @modal.fastapi_endpoint(method="POST", docs=True)
    def chat_completions(self, request: ChatRequest):
        """OpenAI-compatible /v1/chat/completions endpoint with streaming support."""
        if request.stream:
            # Streaming response
            async def event_generator() -> AsyncGenerator[str, None]:
                chunk_id = f"cris-{int(time.time())}"
                try:
                    for full_text in self.generate_stream.remote_gen(
                        request.messages,
                        request.max_tokens,
                        request.temperature,
                    ):
                        chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "model": MODEL_ID,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": full_text},
                                "finish_reason": None,
                            }],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

                    # Final chunk
                    final_chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "model": MODEL_ID,
                        "choices": [{
                            "index": 0,
                            "delta": {},
                            "finish_reason": "stop",
                        }],
                    }
                    yield f"data: {json.dumps(final_chunk)}\n\n"
                    yield "data: [DONE]\n\n"
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    yield "data: [DONE]\n\n"

            return StreamingResponse(event_generator(), media_type="text/event-stream")
        else:
            # Non-streaming response (original behavior)
            result = self.generate.remote(
                request.messages,
                request.max_tokens,
                request.temperature,
            )

            return ChatResponse(
                id="cris-" + str(hash(str(request.messages)))[:8],
                object="chat.completion",
                model=MODEL_ID,
                choices=[{
                    "index": 0,
                    "message": {
                        "role": "assistant",
                        "content": result["content"],
                    },
                    "finish_reason": "stop",
                }],
                usage={
                    "total_tokens": result["tokens_used"],
                },
            )


@app.local_entrypoint()
def test():
    """Quick test of the deployed model."""
    model = ZiraResearcher()
    result = model.generate.remote(
        messages=[
            {"role": "user", "content": "What are the key principles of cross-domain research synthesis?"}
        ],
        max_tokens=512,
    )
    print(f"\nResponse:\n{result['content'][:500]}...")
    print(f"\nTokens used: {result['tokens_used']}")
