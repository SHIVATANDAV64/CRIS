"""
Modal App — FINAL-Bench/Darwin-36B-Opus via vLLM with OpenAI-compatible endpoint and streaming.

Base model: Qwen/Qwen3.6-35B-A3B (vLLM config inherited)
Fine-tuned model: FINAL-Bench/Darwin-36B-Opus
GPU: NVIDIA RTX PRO 6000 — 96 GB GDDR7

Deploy with: modal deploy modal_deploy/modal_app_template.py
"""
import modal
import json
import time
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator

# ─ Modal App Setup ────────────────────────────────────────────────────────

app = modal.App("cris-darwin-opus")

image = modal.Image.debian_slim(python_version="3.11").pip_install(
    "vllm>=0.7.0",
    "fastapi[standard]",
    "transformers>=4.45.0",
    "pydantic>=2.0",
)

# Model config
MODEL_ID = "FINAL-Bench/Darwin-36B-Opus"
BASE_MODEL_ID = "Qwen/Qwen3.6-35B-A3B"

VLLM_ENGINE_ARGS = {
    "tensor_parallel_size": 1,
    "max_model_len": 32768,
    "gpu_memory_utilization": 0.95,
    "enforce_eager": False,
    "trust_remote_code": True,
    "limit_mm_per_prompt": {"image": 0, "video": 0, "audio": 0},
}

# ── Request/Response Models (OpenAI-compatible) ────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = MODEL_ID
    max_tokens: Optional[int] = 8192
    temperature: Optional[float] = 0.7
    top_p: Optional[float] = 0.95
    stream: Optional[bool] = False

# ─ Model Server Class ─────────────────────────────────────────────────────

@app.cls(
    gpu="RTX-PRO-6000",
    image=image,
    timeout=600,
    volumes={
        "/model-cache": modal.Volume.from_name("cris-model-cache", create_if_missing=True),
    },
)
class ModelServer:
    @modal.enter()
    def load_model(self):
        from vllm import LLM, SamplingParams
        from transformers import AutoTokenizer

        print(f"Loading tokenizer from base model: {BASE_MODEL_ID}")
        self.tokenizer = AutoTokenizer.from_pretrained(
            BASE_MODEL_ID,
            trust_remote_code=True,
            cache_dir="/model-cache",
        )

        print(f"Loading fine-tuned model with vLLM: {MODEL_ID}")
        self.llm = LLM(
            model=MODEL_ID,
            download_dir="/model-cache",
            **VLLM_ENGINE_ARGS,
        )
        print("Model loaded successfully!")

    @modal.method()
    def generate(self, prompt: str, max_tokens: int, temperature: float, top_p: float) -> str:
        from vllm import SamplingParams

        sampling_params = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_token_ids=[self.tokenizer.eos_token_id],
        )

        outputs = self.llm.generate(prompt, sampling_params=sampling_params)
        return outputs[0].outputs[0].text

    @modal.method()
    def generate_stream(self, prompt: str, max_tokens: int, temperature: float, top_p: float):
        from vllm import SamplingParams

        sampling_params = SamplingParams(
            max_tokens=max_tokens,
            temperature=temperature,
            top_p=top_p,
            stop_token_ids=[self.tokenizer.eos_token_id],
        )

        full_text = ""
        for request_output in self.llm.generate(prompt, sampling_params=sampling_params, stream=True):
            for output in request_output.outputs:
                full_text = output.text
                yield full_text

# ── FastAPI Web Endpoint ───────────────────────────────────────────────────

@app.function(
    gpu="RTX-PRO-6000",
    image=image,
    timeout=600,
)
@modal.fastapi_endpoint()
def serve():
    api = FastAPI(title="CRIS Darwin-36B-Opus API")
    model = ModelServer()

    @api.get("/health")
    async def health():
        return {"status": "ok", "model": MODEL_ID}

    @api.post("/v1/chat/completions")
    async def chat_completions(req: ChatCompletionRequest):
        messages = [{"role": m.role, "content": m.content} for m in req.messages]
        prompt = model.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )

        if req.stream:
            async def event_generator():
                chunk_id = f"chatcmpl-{int(time.time())}"
                try:
                    for full_text in model.generate_stream.remote_gen(
                        prompt=prompt,
                        max_tokens=req.max_tokens,
                        temperature=req.temperature,
                        top_p=req.top_p,
                    ):
                        chunk = {
                            "id": chunk_id,
                            "object": "chat.completion.chunk",
                            "model": req.model,
                            "choices": [{
                                "index": 0,
                                "delta": {"content": full_text},
                                "finish_reason": None,
                            }],
                        }
                        yield f"data: {json.dumps(chunk)}\n\n"

                    final_chunk = {
                        "id": chunk_id,
                        "object": "chat.completion.chunk",
                        "model": req.model,
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
            full_response = model.generate.remote(
                prompt=prompt,
                max_tokens=req.max_tokens,
                temperature=req.temperature,
                top_p=req.top_p,
            )
            return {
                "id": f"chatcmpl-{int(time.time())}",
                "object": "chat.completion",
                "model": req.model,
                "choices": [{
                    "index": 0,
                    "message": {"role": "assistant", "content": full_response},
                    "finish_reason": "stop",
                }],
                "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
            }

    return api
