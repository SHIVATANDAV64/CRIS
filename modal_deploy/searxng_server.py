"""
Modal.com Deployment — Lightweight Web Search Service

Uses DuckDuckGo, arXiv, and Wikipedia APIs directly instead of SearXNG.
Far more reliable on serverless platforms.

Response format matches what core/searxng_client.py expects:
    {"results": [{"title": ..., "url": ..., "content": ..., "engine": ..., "category": ...}]}

Deploy with:
    modal deploy modal_deploy/searxng_server.py

Test with:
    curl "https://<workspace>--cris-searxng-searxng-server.modal.run/search?q=latest+AI+news&format=json"
"""
import re
import concurrent.futures
import modal

app = modal.App("cris-searxng")

# ── Image ────────────────────────────────────────────────────────────────

image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install(
        "fastapi",
        "ddgs",
        "arxiv",
        "httpx",
    )
)


# ── Search Functions ─────────────────────────────────────────────────────

def _search_duckduckgo(query: str, max_results: int = 10) -> list:
    """Search via DuckDuckGo (general web)."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "content": r.get("body", ""),
                    "engine": "duckduckgo",
                    "category": "general",
                })
        return results
    except Exception as e:
        print(f"[DDG] Error: {e}")
        return []


def _search_ddg_news(query: str, max_results: int = 5) -> list:
    """Search via DuckDuckGo News."""
    try:
        try:
            from ddgs import DDGS
        except ImportError:
            from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.news(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("url", ""),
                    "content": r.get("body", ""),
                    "engine": "duckduckgo_news",
                    "category": "news",
                    "publishedDate": r.get("date", ""),
                })
        return results
    except Exception as e:
        print(f"[DDG News] Error: {e}")
        return []


def _search_arxiv_api(query: str, max_results: int = 5) -> list:
    """Search academic papers via arXiv API."""
    try:
        import arxiv
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = []
        for paper in client.results(search):
            results.append({
                "title": paper.title,
                "url": paper.entry_id,
                "content": paper.summary[:500] if paper.summary else "",
                "engine": "arxiv",
                "category": "science",
                "publishedDate": paper.published.isoformat() if paper.published else "",
            })
        return results
    except Exception as e:
        print(f"[arXiv] Error: {e}")
        return []


def _search_wikipedia(query: str, max_results: int = 3) -> list:
    """Search Wikipedia via its REST API."""
    try:
        import httpx
        resp = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "query",
                "list": "search",
                "srsearch": query,
                "srlimit": max_results,
                "format": "json",
            },
            headers={"User-Agent": "CRIS-Research-Bot/2.0 (research assistant; contact: papireddy199@gmail.com)"},
            timeout=10.0,
        )
        resp.raise_for_status()
        data = resp.json()
        results = []
        for r in data.get("query", {}).get("search", []):
            snippet = re.sub(r"<[^>]+>", "", r.get("snippet", ""))
            results.append({
                "title": r.get("title", ""),
                "url": f"https://en.wikipedia.org/wiki/{r['title'].replace(' ', '_')}",
                "content": snippet,
                "engine": "wikipedia",
                "category": "general",
            })
        return results
    except Exception as e:
        print(f"[Wikipedia] Error: {e}")
        return []


# ── FastAPI App (served via @modal.asgi_app) ─────────────────────────────

from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse

web_app = FastAPI(title="CRIS Web Search", version="2.0")


@web_app.get("/search")
async def search(
    q: str = Query(..., description="Search query"),
    format: str = Query("json", description="Response format"),
    max_results: int = Query(10, description="Max results per engine"),
    engines: str = Query(None, description="Comma-separated engine list"),
    categories: str = Query(None, description="Comma-separated categories"),
    time_range: str = Query(None, description="Time range filter"),
):
    """Multi-engine search endpoint (SearXNG-compatible response format)."""
    if engines:
        engine_list = [e.strip().lower() for e in engines.split(",")]
    else:
        engine_list = ["duckduckgo", "arxiv", "wikipedia", "duckduckgo_news"]

    cat_list = [c.strip() for c in categories.split(",")] if categories else []
    all_results = []

    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
        futures = {}

        if "duckduckgo" in engine_list or "general" in cat_list:
            futures["ddg"] = executor.submit(_search_duckduckgo, q, max_results)

        if "duckduckgo_news" in engine_list or "news" in cat_list:
            futures["news"] = executor.submit(_search_ddg_news, q, min(max_results, 5))

        if "arxiv" in engine_list or "science" in cat_list or "academic" in cat_list:
            futures["arxiv"] = executor.submit(_search_arxiv_api, q, min(max_results, 5))

        if "wikipedia" in engine_list:
            futures["wiki"] = executor.submit(_search_wikipedia, q, min(max_results, 3))

        for key, future in futures.items():
            try:
                results = future.result(timeout=15)
                all_results.extend(results)
            except Exception as e:
                print(f"[{key}] Timeout/error: {e}")

    return JSONResponse(content={
        "query": q,
        "number_of_results": len(all_results),
        "results": all_results,
    })


@web_app.get("/health")
async def health():
    return {"status": "ok"}


@web_app.get("/")
async def root():
    return {"service": "CRIS Web Search", "version": "2.0", "status": "running"}


# ── Modal ASGI Entrypoint ────────────────────────────────────────────────

@app.function(
    image=image,
    cpu=1.0,
    memory=512,
    scaledown_window=300,
    timeout=120,
    max_containers=10,
)
@modal.asgi_app()
def searxng_server():
    """Serve the FastAPI app directly via Modal's ASGI integration."""
    return web_app


@app.local_entrypoint()
def test():
    """Test the search endpoint."""
    print("Deploy with: modal deploy modal_deploy/searxng_server.py")
    print("\nTest with:")
    print('  curl "https://<workspace>--cris-searxng-searxng-server.modal.run/search?q=latest+AI+news&format=json"')
