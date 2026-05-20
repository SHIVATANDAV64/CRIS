from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from core.search_engine import create_index
from core.chat_store import init_chat_store
from server.errors import setup_exception_handlers

# Import routers
from server.routers.chat import router as chat_router
from server.routers.sessions import router as sessions_router
from server.routers.search import router as search_router
from server.routers.wiki import router as wiki_router
from server.routers.settings import router as settings_router
from server.routers.web import router as web_router

app = FastAPI(
    title="CRIS API",
    description="Cognitive Research & Intelligence System Backend API",
    version="3.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For dev, restrict in prod
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Exception Handlers
setup_exception_handlers(app)

# Include Routers
app.include_router(chat_router)
app.include_router(sessions_router)
app.include_router(search_router)
app.include_router(wiki_router)
app.include_router(settings_router)
app.include_router(web_router)

# Research Intelligence Router (Phase 2)
from server.routers.research import router as research_router
app.include_router(research_router)

# Static and Templates
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")


@app.on_event("startup")
async def startup_event():
    """Initialize search index and chat store on startup."""
    create_index()
    init_chat_store()


@app.get("/", tags=["UI"])
async def index(request: Request):
    """Serve the chat interface."""
    return templates.TemplateResponse(request, "index.html")
