"""
CRIS Configuration — All paths, API settings, and model config in one place.
Editable via the Settings UI in the web interface.
"""
import os
import json
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
CONFIG_FILE = BASE_DIR / "config" / "user_config.json"

for d in [RAW_DIR, WIKI_DIR, SOURCES_DIR, CONCEPTS_DIR, ENTITIES_DIR, MODELS_DIR]:
    d.mkdir(parents=True, exist_ok=True)

# ── Default Configuration ──────────────────────────────────────────────────
_DEFAULTS = {
    "arxiv": {
        "oai_url": "http://export.arxiv.org/oai2",
        "rate_limit_seconds": 3,
        "categories": ["cs.AI", "cs.CL", "cs.LG", "q-bio.BM"],
        "max_papers_per_fetch": 100,
    },
    "bedrock": {
        "api_key": os.getenv("BEDROCK_API_KEY", ""),
        "region": os.getenv("BEDROCK_REGION", "us-east-1"),
        "base_url": f"https://bedrock-mantle.{os.getenv('BEDROCK_REGION', 'us-east-1')}.api.aws/v1",
        "model": "minimax.minimax-m2.5",
    },
    "model": {
        "modal_api_url": os.getenv("MODAL_API_URL", "https://naveen95190--cris-darwin-opus-darwinopus-chat-completions.modal.run"),
        "modal_model": "FINAL-Bench/Darwin-36B-Opus",
        "base_model": "Qwen/Qwen3.6-35B-A3B",
        "max_tokens": 32768,
        "temperature": 0.7,
        "top_p": 0.95,
    },
    "chat": {
        "max_history_messages": 20,
        "context_exchanges": 3,
        "max_thinking_length": 8000,
        "streaming_enabled": True,
    },
    "search": {
        "results_limit": 20,
        "context_entries_limit": 15,
    },
    "server": {
        "host": "0.0.0.0",
        "port": 8000,
    },
    "wiki": {
        "compiler_max_tokens": 8192,
        "compiler_temperature": 0.7,
    },
}

# ── User Config Override ───────────────────────────────────────────────────
def _load_user_config() -> dict:
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {}


def _save_user_config(config: dict):
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


_user_config = _load_user_config()
_config = _deep_merge(_DEFAULTS, _user_config)


def get_config() -> dict:
    return _config


def get_config_section(section: str) -> dict:
    return _config.get(section, {})


def update_config(updates: dict) -> dict:
    global _config, _user_config
    _user_config = _deep_merge(_user_config, updates)
    _config = _deep_merge(_DEFAULTS, _user_config)
    _save_user_config(_user_config)
    return _config


def reset_config() -> dict:
    global _config, _user_config
    if CONFIG_FILE.exists():
        CONFIG_FILE.unlink()
    _user_config = {}
    _config = _DEFAULTS.copy()
    return _config


# ── Backward Compatibility Exports ─────────────────────────────────────────

BEDROCK_API_KEY = _config["bedrock"]["api_key"]
BEDROCK_REGION = _config["bedrock"]["region"]
BEDROCK_BASE_URL = _config["bedrock"]["base_url"]
BEDROCK_MODEL = _config["bedrock"]["model"]

ARXIV_OAI_URL = _config["arxiv"]["oai_url"]
ARXIV_RATE_LIMIT_SECONDS = _config["arxiv"]["rate_limit_seconds"]
ARXIV_CATEGORIES = _config["arxiv"]["categories"]

MODAL_API_URL = _config["model"]["modal_api_url"]
MODAL_MODEL = _config["model"]["modal_model"]
BASE_MODEL = _config["model"].get("base_model", "Qwen/Qwen3.6-35B-A3B")

COMPILER_MODEL = BEDROCK_MODEL
COMPILER_MAX_TOKENS = _config["wiki"]["compiler_max_tokens"]
COMPILER_TEMPERATURE = _config["wiki"]["compiler_temperature"]

REASONING_MODEL_ID = _config["model"]["modal_model"]
REASONING_MAX_TOKENS = _config["model"]["max_tokens"]
REASONING_TEMPERATURE = _config["model"]["temperature"]
REASONING_TOP_P = _config["model"]["top_p"]

SEARCH_RESULTS_LIMIT = _config["search"]["results_limit"]
CONTEXT_ENTRIES_LIMIT = _config["search"]["context_entries_limit"]

SERVER_HOST = _config["server"]["host"]
SERVER_PORT = _config["server"]["port"]

MAX_HISTORY_MESSAGES = _config["chat"]["max_history_messages"]
MAX_THINKING_LENGTH = _config["chat"]["max_thinking_length"]
