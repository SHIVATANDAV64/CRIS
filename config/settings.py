"""
CRIS Configuration — All paths, API settings, and model config in one place.
"""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── Project Paths ──────────────────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
WIKI_DIR = DATA_DIR / "wiki"
SOURCES_DIR = WIKI_DIR / "sources"
CONCEPTS_DIR = WIKI_DIR / "concepts"
ENTITIES_DIR = WIKI_DIR / "entities"
DB_PATH = DATA_DIR / "cris.db"
MODELS_DIR = BASE_DIR / "models"

# Ensure directories exist
for d in [RAW_DIR, WIKI_DIR, SOURCES_DIR, CONCEPTS_DIR, ENTITIES_DIR, MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── arXiv Ingestion ────────────────────────────────────────────────────────
ARXIV_OAI_URL = "http://export.arxiv.org/oai2"
ARXIV_RATE_LIMIT_SECONDS = 3

# Default categories for paper ingestion
# cs.AI = Artificial Intelligence
# cs.CL = Computation and Language (NLP)
# cs.LG = Machine Learning
# q-bio.BM = Biomolecular (cross-domain showcase)
ARXIV_CATEGORIES = [
    "cs.AI",
    "cs.CL",
    "cs.LG",
    "q-bio.BM",
]

# ── Modal.com (zira-researcher via OpenAI-compatible endpoint) ──────────
# Deployed on Modal.com — serverless GPU inference
# Endpoint: https://cris-zira-researcher--chat-completions.modal.run
MODAL_API_URL = os.getenv("MODAL_API_URL", "https://cris-zira-researcher--chat-completions.modal.run")
MODAL_MODEL = "0xvoid0000/zira-researcher"

# ── Wiki Compilation Settings (uses Modal zira-researcher) ──────────────
COMPILER_MODEL = MODAL_MODEL
COMPILER_MAX_TOKENS = 4096
COMPILER_TEMPERATURE = 0.7

# ── Reasoning / Chat Settings (uses Modal zira-researcher) ──────────────
REASONING_MODEL_ID = MODAL_MODEL
REASONING_MAX_TOKENS = 4096
REASONING_TEMPERATURE = 0.7
REASONING_TOP_P = 0.95

# ── Local Fallback (if running locally on GPU) ────────────────────────────
REASONING_MODEL_GGUF = "mradermacher/zira-researcher-GGUF"
LOCAL_MODEL_PATH = MODELS_DIR / "zira-researcher-Q4_K_M.gguf"
USE_LOCAL_MODEL = os.getenv("USE_LOCAL_MODEL", "false").lower() == "true"
LOCAL_N_GPU_LAYERS = -1  # -1 = offload everything to GPU
LOCAL_N_CTX = 8192  # Limited by 4GB VRAM

# ── Search Settings ───────────────────────────────────────────────────────
SEARCH_RESULTS_LIMIT = 20
CONTEXT_ENTRIES_LIMIT = 15  # Max wiki entries fed to reasoning model

# ── Server Settings ───────────────────────────────────────────────────────
SERVER_HOST = "0.0.0.0"
SERVER_PORT = 8000
