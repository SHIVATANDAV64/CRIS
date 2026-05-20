"""
Research Intelligence Router — Cross-domain discovery and hybrid search.
Exposes research_service.py functionality through REST API.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional

from core.embedding_client import hybrid_engine, embed_client
from server.services.research_service import research_service

router = APIRouter(tags=["Research Intelligence"])


class HybridSearchRequest(BaseModel):
    query: str
    limit: int = 20
    alpha: float = 0.5  # 0 = BM25 only, 1 = semantic only
    mode: str = "hybrid"  # keyword, semantic, hybrid


class HybridSearchResponse(BaseModel):
    query: str
    mode: str
    count: int
    results: list[dict]


class CrossDomainDiscoveryRequest(BaseModel):
    arxiv_id: str
    source_domain: str
    target_domains: List[str]
    top_k: int = 10


class CrossDomainConnection(BaseModel):
    id: str
    title: str
    domain: str
    similarity: float
    abstract: str = ""


class CrossDomainDiscoveryResponse(BaseModel):
    source: str
    source_domain: str
    connections: List[CrossDomainConnection]


class DecomposeRequest(BaseModel):
    query: str
    depth: str = "shallow"  # shallow, medium, deep
    model_id: Optional[str] = None


class DecomposeResponse(BaseModel):
    decomposition_id: str
    original_query: str
    depth: str
    literature_queries: List[str]
    hypothesis_candidates: List[str]
    method_analysis_targets: List[str]
    cross_domain_pairs: List[dict]


class SynthesizeRequest(BaseModel):
    question: str
    source_ids: List[str]
    model_id: Optional[str] = None


class SynthesizeResponse(BaseModel):
    question: str
    findings: List[dict]
    summary: str
    sources_used: int


@router.post("/api/research/hybrid-search", response_model=HybridSearchResponse)
async def hybrid_search(req: HybridSearchRequest):
    """
    Hybrid search combining BM25 (FTS5) and semantic (embedding) search.

    - mode=keyword: Pure BM25/FTS5 search
    - mode=semantic: Pure embedding similarity
    - mode=hybrid: Combined ranking
    """
    try:
        if not embed_client.is_available():
            # Fallback to keyword search
            from core.search_engine import search
            results = search(req.query, limit=req.limit)
            return {
                "query": req.query,
                "mode": "keyword",
                "count": len(results),
                "results": results,
            }

        if req.mode == "keyword":
            from core.search_engine import search
            results = search(req.query, limit=req.limit)
            return {
                "query": req.query,
                "mode": "keyword",
                "count": len(results),
                "results": results,
            }

        if req.mode == "semantic":
            # Semantic only: need to embed query and search
            from core.embedding_client import embed_store
            query_embedding = await embed_client.embed_text(req.query)
            results = await embed_store.similarity_search(query_embedding, req.limit)
            # Enrich with paper metadata
            from core.domain_manager import get_paper_by_id
            enriched = []
            for r in results:
                paper = get_paper_by_id(r["arxiv_id"])
                if paper:
                    enriched.append({
                        **paper,
                        "similarity": r["similarity"],
                    })
            return {
                "query": req.query,
                "mode": "semantic",
                "count": len(enriched),
                "results": enriched,
            }

        # Hybrid (default)
        results = await hybrid_engine.hybrid_search(
            req.query, limit=req.limit, alpha=req.alpha
        )
        return {
            "query": req.query,
            "mode": "hybrid",
            "count": len(results),
            "results": results,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")


@router.post("/api/research/cross-domain", response_model=CrossDomainDiscoveryResponse)
async def cross_domain_discovery(req: CrossDomainDiscoveryRequest):
    """
    Discover cross-domain connections for a paper.

    Given a source paper and target domains, find papers in those domains
    with semantically similar mechanisms and concepts.
    """
    try:
        result = await hybrid_engine.cross_domain_discovery(
            arxiv_id=req.arxiv_id,
            source_domain=req.source_domain,
            target_domains=req.target_domains,
            top_k=req.top_k,
        )

        if "error" in result:
            raise HTTPException(status_code=400, detail=result["error"])

        return {
            "source": result["source"],
            "source_domain": result.get("source_domain", ""),
            "connections": result["connections"],
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Discovery failed: {str(e)}")


@router.post("/api/research/decompose", response_model=DecomposeResponse)
async def decompose_query(req: DecomposeRequest):
    """
    Decompose a research question into sub-queries using LLM.

    Returns structured decomposition with:
    - Literature search queries
    - Hypothesis candidates
    - Method analysis targets
    - Cross-domain connection pairs
    """
    try:
        decomposition = await research_service.decompose(
            query=req.query,
            depth=req.depth,
            model_id=req.model_id,
        )

        return {
            "decomposition_id": decomposition.id,
            "original_query": decomposition.original_query,
            "depth": decomposition.depth,
            "literature_queries": decomposition.literature_queries,
            "hypothesis_candidates": decomposition.hypothesis_candidates,
            "method_analysis_targets": decomposition.method_analysis_targets,
            "cross_domain_pairs": decomposition.cross_domain_pairs,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Decomposition failed: {str(e)}")


@router.post("/api/research/synthesize", response_model=SynthesizeResponse)
async def synthesize_evidence(req: SynthesizeRequest):
    """
    Synthesize findings from multiple sources into coherent claims.

    Aggregates findings, resolves contradictions, and produces
    inline citations.
    """
    try:
        # Fetch source papers
        from core.domain_manager import get_paper_by_id
        sources = []
        for arxiv_id in req.source_ids:
            paper = get_paper_by_id(arxiv_id)
            if paper:
                sources.append({
                    "arxiv_id": paper.get("arxiv_id", ""),
                    "title": paper.get("title", ""),
                    "wiki_content": paper.get("abstract", ""),
                })

        result = await research_service.synthesize(
            question=req.question,
            sources=sources,
            model_id=req.model_id,
        )

        return {
            "question": result["question"],
            "findings": result["findings"],
            "summary": result["summary"],
            "sources_used": result["sources_used"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Synthesis failed: {str(e)}")


@router.get("/api/research/embeddings/status")
async def embeddings_status():
    """Check embedding service health and stats."""
    from core.embedding_client import embed_store

    conn = embed_store.db_path
    try:
        import sqlite3
        db = sqlite3.connect(conn)
        cursor = db.cursor()
        cursor.execute("SELECT COUNT(*) FROM paper_embeddings WHERE has_embedding = 1")
        count = cursor.fetchone()[0]
        db.close()
    except Exception:
        count = 0

    return {
        "service_available": embed_client.is_available(),
        "vector_store_available": embed_store._vec_available,
        "indexed_papers": count,
        "embedding_dimension": 2560,
    }


@router.post("/api/research/embeddings/index")
async def index_embeddings(batch_size: int = 32):
    """
    Index embeddings for all papers that don't have them.

    This is a batch job that should be run once or periodically.
    """
    if not embed_client.is_available():
        raise HTTPException(status_code=503, detail="Embedding service not available")

    try:
        from core.search_engine import get_all_entries
        from core.embedding_client import embed_store

        entries = get_all_entries()

        # Find entries without embeddings
        to_index = []
        for entry in entries:
            arxiv_id = entry.get("arxiv_id")
            if arxiv_id:
                existing = await embed_store.get_embedding(arxiv_id)
                if not existing:
                    text = f"{entry.get('title', '')} {entry.get('wiki_content', '')}"
                    if len(text) > 100:
                        to_index.append({"arxiv_id": arxiv_id, "text": text[:15000]})

        # Process in batches
        total = len(to_index)
        indexed = 0

        for i in range(0, len(to_index), batch_size):
            batch = to_index[i:i + batch_size]
            texts = [t["text"] for t in batch]

            try:
                embeddings = await embed_client.embed_batch(texts)

                for j, embedding in enumerate(embeddings):
                    await embed_store.store_embedding(batch[j]["arxiv_id"], embedding)

                indexed += len(batch)
                print(f"[index] Progress: {indexed}/{total}")
            except Exception as e:
                print(f"[index] Batch failed: {e}")

        return {
            "total_papers": total,
            "indexed": indexed,
            "service_available": True,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Indexing failed: {str(e)}")
