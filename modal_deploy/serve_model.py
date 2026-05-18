"""
Modal.com Deployment — Serve FINAL-Bench/Darwin-36B-Opus via transformers + OpenAI-compatible API with streaming.

Base model: Qwen/Qwen3.6-35B-A3B
Fine-tuned model: FINAL-Bench/Darwin-36B-Opus
GPU: NVIDIA RTX PRO 6000 — 96 GB GDDR7

Deploy with:
    modal deploy modal_deploy/serve_model.py
"""
import modal
import json
import time
import asyncio
from threading import Thread
from pydantic import BaseModel
from typing import Optional, AsyncGenerator
from fastapi.responses import StreamingResponse

app = modal.App("cris-darwin-opus")

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "torch>=2.5.0",
        "transformers>=4.51.0",
        "accelerate>=1.0.0",
        "fastapi>=0.115.0",
        "pydantic>=2.0",
    )
)

MODEL_ID = "FINAL-Bench/Darwin-36B-Opus"
BASE_MODEL_ID = "Qwen/Qwen3.6-35B-A3B"


class ChatRequest(BaseModel):
    messages: list[dict]
    max_tokens: int = 8192
    temperature: float = 0.7
    top_p: float = 0.95
    stream: bool = False


class ChatResponse(BaseModel):
    id: str
    object: str
    model: str
    choices: list[dict]
    usage: dict


@app.cls(
    gpu="RTX-PRO-6000",
    image=image,
    scaledown_window=300,
    timeout=600,
    volumes={
        "/model-cache": modal.Volume.from_name("cris-model-cache", create_if_missing=True),
    },
)
class DarwinOpus:
    @modal.enter()
    def load_model(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        self.tokenizer = AutoTokenizer.from_pretrained(
            BASE_MODEL_ID,
            trust_remote_code=True,
            cache_dir="/model-cache",
        )

        self.model = AutoModelForCausalLM.from_pretrained(
            MODEL_ID,
            trust_remote_code=True,
            torch_dtype=torch.bfloat16,
            device_map="auto",
            cache_dir="/model-cache",
        )
        self.model.eval()

    @modal.method()
    def generate(self, messages: list[dict], max_tokens: int = 8192, temperature: float = 0.7, top_p: float = 0.95) -> dict:
        import torch
        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        input_len = inputs["input_ids"].shape[1]

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                top_p=top_p,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        generated_tokens = outputs[0][input_len:]
        text = self.tokenizer.decode(generated_tokens, skip_special_tokens=True)

        return {
            "content": text,
            "tokens_used": len(generated_tokens),
        }

    @modal.method()
    def generate_stream(self, messages: list[dict], max_tokens: int = 8192, temperature: float = 0.7, top_p: float = 0.95):
        """Generate response token-by-token using TextIteratorStreamer for real streaming."""
        import torch
        from transformers import TextIteratorStreamer

        prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)
        input_len = inputs["input_ids"].shape[1]

        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
            timeout=300,
        )

        generation_kwargs = {
            **inputs,
            "max_new_tokens": max_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "do_sample": True,
            "pad_token_id": self.tokenizer.eos_token_id,
            "streamer": streamer,
        }

        thread = Thread(target=self.model.generate, kwargs=generation_kwargs)
        thread.start()

        for new_text in streamer:
            yield new_text

        thread.join()

    @modal.fastapi_endpoint(method="POST", docs=True)
    async def chat_completions(self, request: ChatRequest):
        """OpenAI-compatible /v1/chat/completions endpoint with streaming support."""
        if request.stream:
            async def event_generator() -> AsyncGenerator[str, None]:
                chunk_id = f"cris-{int(time.time())}"
                full_text = ""
                try:
                    async for token in self.generate_stream.remote_gen.aio(
                        request.messages,
                        request.max_tokens,
                        request.temperature,
                        request.top_p,
                    ):
                        full_text += token
                        chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "model": MODEL_ID,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": token},
                                "finish_reason": None,
                            }],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

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
            result = await self.generate.remote.aio(
                request.messages,
                request.max_tokens,
                request.temperature,
                request.top_p,
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
    model = DarwinOpus()
    result = model.generate.remote(
        messages=[
            {"role": "user", "content": "What are the key principles of cross-domain research synthesis?"}
        ],
        max_tokens=512,
    )
    print(f"\nResponse:\n{result['content'][:500]}...")
    print(f"\nTokens used: {result['tokens_used']}")
