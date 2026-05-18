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
