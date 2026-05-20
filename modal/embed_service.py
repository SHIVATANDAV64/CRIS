"""
Modal Embeddings Service — pplx-embed-v1-4b on T4 GPU
Deploys Text Embeddings Inference for production-grade embeddings.
"""
import modal
import os

# Create Modal app
app = modal.App("cris-embeddings")

# Image with TEI (Text Embeddings Inference)
teibuild = modal.Image.from_registry(
    "ghcr.io/huggingface/text-embeddings-inference:1.9",
    add_python="3.11",
)

# Model ID
MODEL_ID = "perplexity-ai/pplx-embed-v1-4B"
HF_TOKEN = os.environ.get("HF_TOKEN", "")

# Snapshot directory for caching
MODEL_DIR = "/model"


@app.cls(
    gpu="T4",
    image=modal.Image.debian_slim()
    .apt_install("curl", "git", "git-lfs", "libcublas11", "libcudnn8")
    .pip_install("sentence-transformers", "huggingface-hub", "requests"),
    secrets=[modal.Secret.from_name("cris-secrets")] if modal.is_local() else [],
    timeout=600,
    min_containers=0,
    max_containers=5,
)
class EmbedService:
    """
    Embedding service using pplx-embed-v1-4b.
    Runs on T4 GPU for optimal performance/cost ratio.
    """

    @modal.enter()
    def setup(self):
        """Load model on startup."""
        from sentence_transformers import SentenceTransformer
        import torch

        print("[embed] Loading pplx-embed-v1-4b...")
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"[embed] Device: {self.device}")

        # Load model
        self.model = SentenceTransformer(
            MODEL_ID,
            device=self.device,
            trust_remote_code=True,
        )
        self.dimension = 2560
        print(f"[embed] Model loaded. Dimension: {self.dimension}")

    @modal.method()
    def embed_text(self, text: str) -> list[float]:
        """Embed a single text."""
        import torch
        with torch.no_grad():
            embedding = self.model.encode(text, normalize_embeddings=True)
        return embedding.tolist()

    @modal.method()
    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        """Embed multiple texts in batch (more efficient)."""
        import torch
        with torch.no_grad():
            embeddings = self.model.encode(
                texts,
                batch_size=32,
                normalize_embeddings=True,
                show_progress_bar=False,
            )
        return embeddings.tolist()

    @modal.method()
    def embed_with_binary(self, texts: list[str], binary: bool = False) -> dict:
        """Embed with optional binary quantization."""
        import torch
        import numpy as np

        with torch.no_grad():
            embeddings = self.model.encode(
                texts,
                batch_size=32,
                normalize_embeddings=True,
            )

        result = {
            "float": embeddings.tolist(),
            "dimension": self.dimension,
        }

        if binary:
            # Binary quantization: pack bits into bytes
            binary_vecs = (embeddings > 0).astype(np.uint8)
            packed = np.packbits(binary_vecs, axis=1)
            result["binary"] = packed.tolist()
            result["binary_packed_dim"] = packed.shape[1]

        return result

    @modal.method()
    def similarity(self, text1: str, text2: str) -> float:
        """Compute cosine similarity between two texts."""
        import torch
        import numpy as np

        with torch.no_grad():
            embeddings = self.model.encode([text1, text2], normalize_embeddings=True)

        # Cosine similarity (already normalized)
        sim = np.dot(embeddings[0], embeddings[1])
        return float(sim)

    @modal.method()
    def cross_domain_similarity(
        self,
        source_text: str,
        candidates: list[dict],
    ) -> list[dict]:
        """
        Find cross-domain similar papers.

        Args:
            source_text: Query or source paper abstract
            candidates: List of {id, text, domain} dicts

        Returns:
            Sorted list with similarity scores, domain-agnostic
        """
        import torch
        import numpy as np

        texts = [source_text] + [c["text"] for c in candidates]

        with torch.no_grad():
            embeddings = self.model.encode(texts, batch_size=32, normalize_embeddings=True)

        source_vec = embeddings[0]
        candidate_vecs = embeddings[1:]

        # Compute similarities
        similarities = np.dot(candidate_vecs, source_vec)

        results = []
        for i, candidate in enumerate(candidates):
            results.append({
                "id": candidate["id"],
                "domain": candidate.get("domain", "unknown"),
                "similarity": float(similarities[i]),
            })

        # Sort by similarity descending
        results.sort(key=lambda x: x["similarity"], reverse=True)
        return results

    @modal.method()
    def health(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "model": MODEL_ID,
            "dimension": self.dimension,
            "device": self.device,
        }


# Web endpoint for external access
@app.function(
    image=modal.Image.debian_slim().pip_install("fastapi", "uvicorn"),
    min_containers=0,
    max_containers=5,
)
@modal.asgi_app()
def web():
    """FastAPI web interface for embeddings."""
    from fastapi import FastAPI, HTTPException
    from pydantic import BaseModel
    from typing import List

    web_app = FastAPI(title="CRIS Embeddings API")
    service = EmbedService()

    class EmbedRequest(BaseModel):
        texts: List[str]
        binary: bool = False

    class SimilarityRequest(BaseModel):
        text1: str
        text2: str

    class CrossDomainRequest(BaseModel):
        source_text: str
        candidates: List[dict]

    @web_app.post("/embed")
    async def embed(req: EmbedRequest):
        if not req.texts:
            raise HTTPException(status_code=400, detail="No texts provided")
        if len(req.texts) == 1:
            embedding = service.embed_text.remote(req.texts[0])
            return {"embeddings": [embedding], "dimension": 2560}
        result = service.embed_with_binary.remote(req.texts, req.binary)
        return result

    @web_app.post("/similarity")
    async def similarity(req: SimilarityRequest):
        sim = service.similarity.remote(req.text1, req.text2)
        return {"similarity": sim}

    @web_app.post("/cross-domain")
    async def cross_domain(req: CrossDomainRequest):
        results = service.cross_domain_similarity.remote(req.source_text, req.candidates)
        return {"results": results}

    @web_app.get("/health")
    async def health():
        return service.health.remote()

    return web_app


if __name__ == "__main__":
    # Local testing
    print("Modal app defined. Deploy with: modal deploy modal/embed_service.py")
