from fastapi import APIRouter

from config.settings import SEARXNG_MODAL_URL
from core.web_tools import get_scraper, get_search
from server.models.schemas import WebSearchRequest, WebScrapeRequest

router = APIRouter(tags=["Web & Scraper"])


@router.post("/api/web/search")
async def web_search(req: WebSearchRequest):
    """Search the web via SearXNG with quality filtering."""
    options = {
        "max_results": req.num_results,
        "min_credibility": req.min_credibility,
    }
    if req.time_range:
        options["time_range"] = req.time_range
    if req.categories:
        options["categories"] = req.categories
    if req.engines:
        options["engines"] = req.engines

    search = get_search(SEARXNG_MODAL_URL)
    results = await search.search(req.query, req.num_results, options=options)
    return {"query": req.query, "count": len(results), "results": results}


@router.post("/api/web/scrape")
async def web_scrape(req: WebScrapeRequest):
    """Scrape a URL and return cleaned content."""
    scraper = get_scraper()
    result = await scraper.scrape_url(req.url)
    return result


@router.post("/api/web/search-and-scrape")
async def web_search_and_scrape(req: WebSearchRequest):
    """Search the web and scrape top results."""
    search = get_search(SEARXNG_MODAL_URL)
    results = await search.search_and_scrape(req.query, req.num_results)
    return {"query": req.query, "count": len(results), "results": results}
