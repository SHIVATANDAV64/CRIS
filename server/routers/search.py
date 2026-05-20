from fastapi import APIRouter, Depends, HTTPException

from server.services.search_service import SearchService
from server.dependencies import get_search_service

router = APIRouter(tags=["Search & Domains"])


@router.get("/api/domains")
async def list_domains(search_service: SearchService = Depends(get_search_service)):
    """List all domains with paper counts."""
    domains = search_service.list_domains()
    return {"count": len(domains), "domains": domains}


@router.get("/api/domains/{domain}/papers")
async def get_domain_papers(domain: str, search_service: SearchService = Depends(get_search_service)):
    """Get all papers for a domain, grouped by date."""
    papers = search_service.get_domain_papers(domain)
    return {"domain": domain, "date_groups": papers}


@router.get("/api/domains/{domain}/papers/{date}/{paper_id}")
async def get_paper(domain: str, date: str, paper_id: str, search_service: SearchService = Depends(get_search_service)):
    """Get a specific paper's full details."""
    paper = search_service.get_paper_detail(domain, date, paper_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.post("/api/raw-sources/migrate")
async def migrate_sources(search_service: SearchService = Depends(get_search_service)):
    """Migrate existing papers from date-based to domain-based storage."""
    counts = search_service.migrate_sources()
    return {"migrated": counts, "total": sum(counts.values())}


@router.get("/api/raw-sources")
async def list_raw_sources(search_service: SearchService = Depends(get_search_service)):
    """Get all raw papers organized by date and category."""
    sources = search_service.list_raw_sources()
    return {"count": sum(g.get("paper_count", 0) for g in sources), "date_groups": sources}


@router.get("/api/raw-sources/{arxiv_id}")
async def get_raw_paper(arxiv_id: str, search_service: SearchService = Depends(get_search_service)):
    """Get a specific raw paper by arXiv ID."""
    paper = search_service.get_raw_paper(arxiv_id)
    if not paper:
        raise HTTPException(status_code=404, detail="Paper not found")
    return paper


@router.get("/api/stats")
async def stats(search_service: SearchService = Depends(get_search_service)):
    """Get knowledge base statistics."""
    return search_service.get_stats()


@router.get("/api/search")
async def search_papers(q: str, limit: int = 20, search_service: SearchService = Depends(get_search_service)):
    """Direct search endpoint."""
    results = search_service.search_papers(q, limit=limit)
    return {"query": q, "count": len(results), "results": results}


@router.get("/api/papers")
async def list_papers(limit: int = 50, search_service: SearchService = Depends(get_search_service)):
    """List all papers in the knowledge base."""
    entries = search_service.list_papers(limit=limit)
    return {"count": len(entries), "papers": entries}


# ─────────────────────────────────────────────────────────────────────────
# Phase 5: Hybrid Search + Citation Graph + Research Plans
# ─────────────────────────────────────────────────────────────────────────

import sqlite3
import json
from pathlib import Path
from config.settings import DATA_DIR


def _get_db():
    """Get database connection."""
    db_path = Path(DATA_DIR) / "cris.db"
    return sqlite3.connect(db_path)


@router.post("/api/search/hybrid")
async def hybrid_search(q: str, mode: str = "hybrid", limit: int = 20):
    """
    Hybrid search: keyword (BM25) + semantic (embeddings).

    - mode=keyword: Pure BM25/FTS5 search
    - mode=semantic: Embedding similarity (when available)
    - mode=hybrid: Combined scoring (0.4 keyword + 0.6 semantic)
    """
    from core.search_engine import search as keyword_search

    # Keyword results (BM25)
    keyword_results = keyword_search(q, limit=limit * 2)

    if mode == "keyword":
        return {"mode": "keyword", "query": q, "results": keyword_results[:limit]}

    # Semantic would use sentence-transformers - placeholder for now
    semantic_results = []

    if mode == "semantic":
        return {"mode": "semantic", "query": q, "results": []}

    # Hybrid: Weighted RRF
    scores = {}
    for rank, item in enumerate(keyword_results):
        key = item.get("arxiv_id", str(rank))
        scores[key] = {"item": item, "score": 0}
        scores[key]["score"] += 0.4 * (1 / (60 + rank + 1))

    for rank, item in enumerate(semantic_results):
        key = item.get("arxiv_id", str(rank))
        if key not in scores:
            scores[key] = {"item": item, "score": 0}
        scores[key]["score"] += 0.6 * (1 / (60 + rank + 1))

    sorted_results = sorted(scores.values(), key=lambda x: x["score"], reverse=True)

    return {
        "mode": "hybrid",
        "query": q,
        "results": [s["item"] for s in sorted_results[:limit]],
    }


@router.get("/api/graph/citations/{paper_id}")
async def get_citation_graph(paper_id: str):
    """Get citation graph for a paper (papers it cites and that cite it)."""
    conn = _get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT citing_paper FROM citations WHERE cited_paper = ? LIMIT 50
        """, (paper_id,))
        cited_by = [r[0] for r in cursor.fetchall()]

        cursor.execute("""
            SELECT cited_paper FROM citations WHERE citing_paper = ? LIMIT 50
        """, (paper_id,))
        cites = [r[0] for r in cursor.fetchall()]

        return {
            "paper_id": paper_id,
            "cited_by": cited_by,
            "cites": cites,
            "total_citations": len(cited_by),
            "total_references": len(cites),
        }
    except sqlite3.OperationalError:
        return {"paper_id": paper_id, "cited_by": [], "cites": [], "note": "Citation graph not initialized"}
    finally:
        conn.close()


# ─────────────────────────────────────────────────────────────────────────
# Research Plans
# ─────────────────────────────────────────────────────────────────────────

@router.get("/api/plans")
async def list_plans():
    """List all research plans."""
    conn = _get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            SELECT id, title, description, status, created_at FROM research_plans
            ORDER BY updated_at DESC
        """)
        plans = [
            {"id": r[0], "title": r[1], "description": r[2], "status": r[3], "created_at": r[4]}
            for r in cursor.fetchall()
        ]
        return {"plans": plans}
    except sqlite3.OperationalError:
        return {"plans": [], "note": "Research plans not initialized"}
    finally:
        conn.close()


@router.post("/api/plans")
async def create_plan(title: str, description: str = ""):
    """Create a new research plan."""
    import uuid
    plan_id = str(uuid.uuid4())[:8]
    conn = _get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS research_plans (
                id TEXT PRIMARY KEY, title TEXT NOT NULL, description TEXT,
                status TEXT DEFAULT 'draft', created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        cursor.execute("""
            INSERT INTO research_plans (id, title, description) VALUES (?, ?, ?)
        """, (plan_id, title, description))
        conn.commit()
        return {"id": plan_id, "title": title, "status": "draft"}
    finally:
        conn.close()


@router.get("/api/plans/{plan_id}")
async def get_plan(plan_id: str):
    """Get a research plan with hypotheses and tasks."""
    conn = _get_db()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, title, description, status FROM research_plans WHERE id = ?", (plan_id,))
        row = cursor.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Plan not found")

        plan = {"id": row[0], "title": row[1], "description": row[2], "status": row[3], "hypotheses": [], "tasks": []}

        # Hypotheses
        cursor.execute("SELECT id, statement, status FROM hypotheses WHERE plan_id = ?", (plan_id,))
        plan["hypotheses"] = [{"id": r[0], "statement": r[1], "status": r[2]} for r in cursor.fetchall()]

        # Tasks
        cursor.execute("SELECT id, title, status FROM tasks WHERE plan_id = ?", (plan_id,))
        plan["tasks"] = [{"id": r[0], "title": r[1], "status": r[2]} for r in cursor.fetchall()]

        return plan
    finally:
        conn.close()


@router.delete("/api/plans/{plan_id}")
async def delete_plan(plan_id: str):
    """Delete a research plan."""
    conn = _get_db()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM tasks WHERE plan_id = ?", (plan_id,))
    cursor.execute("DELETE FROM hypotheses WHERE plan_id = ?", (plan_id,))
    cursor.execute("DELETE FROM research_plans WHERE id = ?", (plan_id,))
    conn.commit()
    conn.close()
    return {"deleted": True, "id": plan_id}
