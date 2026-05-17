"""
Modal App — OpenAI-compatible LLM endpoint with streaming support.

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

app = modal.App("cris-zira-researcher")

image = modal.Image.debian_slim().pip_install(
    "fastapi[standard]",
    "torch",
    "transformers",
    "accelerate",
)

# ── Request/Response Models (OpenAI-compatible) ────────────────────────────

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[ChatMessage]
    model: Optional[str] = "0xvoid0000/zira-researcher"
    max_tokens: Optional[int] = 4096
    temperature: Optional[float] = 0.7
    stream: Optional[bool] = False

# ─ Model Server Class ─────────────────────────────────────────────────────

@app.cls(
    gpu="T4",
    image=image,
    timeout=300,
)
class ModelServer:
    @modal.enter()
    def load_model(self):
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer

        model_name = "0xvoid0000/zira-researcher"
        print(f"Loading model: {model_name}")

        self.tokenizer = AutoTokenizer.from_pretrained(model_name, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_name,
            torch_dtype=torch.float16,
            device_map="auto",
            trust_remote_code=True,
        )
        print("Model loaded successfully!")

    @modal.method()
    def generate(self, prompt: str, max_tokens: int, temperature: float) -> str:
        import torch

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    @modal.method()
    def generate_stream(self, prompt: str, max_tokens: int, temperature: float):
        import torch

        inputs = self.tokenizer(prompt, return_tensors="pt").to(self.model.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=temperature,
                do_sample=True,
                pad_token_id=self.tokenizer.eos_token_id,
            )

        full_text = ""
        for i in range(1, len(outputs[0])):
            token = self.tokenizer.decode(outputs[0][i], skip_special_tokens=True)
            full_text += token
            yield full_text

# ── FastAPI Web Endpoint ───────────────────────────────────────────────────

@app.function(
    gpu="T4",
    image=image,
    timeout=300,
)
@modal.fastapi_endpoint()
def serve():
    api = FastAPI(title="CRIS Zira Researcher API")
    model = ModelServer()

    @api.get("/health")
    async def health():
        return {"status": "ok"}

    @api.post("/v1/chat/completions")
    async def chat_completions(req: ChatCompletionRequest):
        prompt = ""
        for msg in req.messages:
            if msg.role == "system":
                prompt += f"<|system|>\n{msg.content}\n"
            elif msg.role == "user":
                prompt += f"<|user|>\n{msg.content}\n"
            elif msg.role == "assistant":
                prompt += f"<|assistant|>\n{msg.content}\n"
        prompt += "<|assistant|>\n"

        if req.stream:
            async def event_generator():
                chunk_id = f"chatcmpl-{int(time.time())}"
                try:
                    for full_text in model.generate_stream.remote_gen(
                        prompt=prompt,
                        max_tokens=req.max_tokens,
                        temperature=req.temperature,
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
