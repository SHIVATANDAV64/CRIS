import os
import sys
from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, BackgroundTasks, HTTPException
from pydantic import BaseModel, Field

# Ensure project root is in system path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from core.arxiv_client import fetch_papers, save_papers, save_papers_by_domain
from core.domain_manager import migrate_existing_papers

router = APIRouter(tags=["Scripts Execution"])

class IngestRequest(BaseModel):
    date: Optional[str] = Field(None, description="Fetch papers from this date (YYYY-MM-DD). Defaults to yesterday.")
    days_back: int = Field(0, description="Fetch papers from N days ago up to today.")
    categories: Optional[str] = Field(None, description="Comma-separated arXiv categories (e.g., cs.AI,cs.CL).")
    max_papers: Optional[int] = Field(None, description="Maximum papers per category.")
    domain_mode: bool = Field(True, description="Save papers organized by domain folders.")
    auto_compile: bool = Field(False, description="Automatically compile wiki and rebuild search index after fetching papers.")

import json
from pathlib import Path

# Simple lock & status tracking to prevent running concurrent ingestion tasks and report progress
STATUS_FILE = Path(__file__).resolve().parent.parent.parent / "data" / "ingest_status.json"

def _load_status() -> dict:
    default_status = {
        "running": False,
        "current_date": None,
        "dates_total": 0,
        "dates_processed": 0,
        "papers_fetched": 0,
        "logs": [],
        "error": None,
        "progress_percent": 0
    }
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                data["running"] = False  # If the server is restarting/starting, it cannot be running
                if "progress_percent" not in data:
                    data["progress_percent"] = 0
                return data
        except Exception:
            pass
    return default_status

def _save_status():
    global _ingest_status
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump(_ingest_status, f, indent=2)
    except Exception as e:
        print(f"Error saving ingest status: {e}")

_ingest_running = False
_ingest_cancelled = False
_ingest_status = _load_status()

def _run_ingestion_sync(req: IngestRequest):
    global _ingest_running, _ingest_status, _ingest_cancelled
    _ingest_cancelled = False
    _ingest_status = {
        "running": True,
        "current_date": None,
        "dates_total": 0,
        "dates_processed": 0,
        "papers_fetched": 0,
        "logs": ["Ingestion task initialized."],
        "error": None,
        "progress_percent": 0
    }
    _save_status()
    try:
        # Determine dates
        if req.days_back > 0:
            dates = []
            for i in range(req.days_back, -1, -1):
                d = datetime.now() - timedelta(days=i)
                dates.append(d.strftime("%Y-%m-%d"))
        elif req.date:
            dates = [req.date]
        else:
            yesterday = datetime.now() - timedelta(days=1)
            dates = [yesterday.strftime("%Y-%m-%d")]

        _ingest_status["dates_total"] = len(dates)
        _ingest_status["logs"].append(f"Ingestion queue: {len(dates)} dates to process.")
        _save_status()

        # Parse categories
        categories_list = [c.strip() for c in req.categories.split(",") if c.strip()] if req.categories else None

        print(f"[BACKGROUND TASK] Starting arXiv ingestion for dates: {dates}")
        total_papers = 0

        # Calculate progress parameters
        total_dates = len(dates)
        from config.settings import get_config
        cfg = get_config()
        default_cats = cfg.get("arxiv", {}).get("categories", ["cs.AI", "cs.CL", "cs.LG"])
        total_categories = len(categories_list) if categories_list else len(default_cats)
        total_steps = total_dates * total_categories

        def log_callback(msg: str):
            cleaned = msg.strip()
            if cleaned:
                # Support single-line or multi-line messages split by newline
                for part in cleaned.split("\n"):
                    part_cleaned = part.strip()
                    if part_cleaned:
                        _ingest_status["logs"].append(part_cleaned)
                _save_status()

        def paper_fetched_callback(paper: dict):
            nonlocal total_papers
            total_papers += 1
            _ingest_status["papers_fetched"] = total_papers
            _save_status()

        def category_start_callback(category: str, cat_idx: int, date_idx: int):
            # Calculate dynamic progress
            current_step = (date_idx * total_categories) + cat_idx
            progress = int((current_step / total_steps) * 100)
            _ingest_status["progress_percent"] = min(progress, 99)
            _save_status()

        for idx, date_str in enumerate(dates):
            if _ingest_cancelled:
                _ingest_status["logs"].append("Ingestion task stopped by user.")
                _save_status()
                break

            _ingest_status["current_date"] = date_str
            _ingest_status["logs"].append(f"Fetching papers for date: {date_str}...")
            _save_status()
            print(f"[BACKGROUND TASK] Fetching for date: {date_str}")
            
            papers = fetch_papers(
                from_date=date_str,
                categories=categories_list,
                max_papers=req.max_papers,
                is_cancelled=lambda: _ingest_cancelled,
                on_log=log_callback,
                on_paper_fetched=paper_fetched_callback,
                on_category_start=lambda cat, c_idx, d_idx=idx: category_start_callback(cat, c_idx, d_idx)
            )

            if _ingest_cancelled:
                _ingest_status["logs"].append("Ingestion task stopped by user.")
                _save_status()
                break

            if papers:
                _ingest_status["logs"].append(f"Saving {len(papers)} papers fetched for {date_str}...")
                _save_status()
                if req.domain_mode:
                    save_papers_by_domain(papers, on_log=log_callback)
                else:
                    save_papers(papers, date_str, on_log=log_callback)
                # total_papers is updated dynamically in paper_fetched_callback
                _ingest_status["papers_fetched"] = total_papers
            else:
                _ingest_status["logs"].append(f"No papers found for {date_str}.")
            
            _ingest_status["dates_processed"] = idx + 1
            _save_status()

        if _ingest_cancelled:
            _ingest_status["logs"].append("Ingestion aborted by user.")
        else:
            _ingest_status["logs"].append(f"Ingestion completed successfully! Total papers added to library: {total_papers}")
            _ingest_status["progress_percent"] = 90
            _save_status()
            
            if req.auto_compile:
                log_callback("\n[Auto-Compile] Starting wiki compilation for all unprocessed papers...")
                _ingest_status["progress_percent"] = 92
                _save_status()
                
                import subprocess
                p_compile = subprocess.Popen(
                    [sys.executable, "scripts/compile_wiki.py", "--all"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    bufsize=1,
                    encoding="utf-8",
                    errors="replace",
                    env={**os.environ, "PYTHONUTF8": "1"}
                )
                for line in iter(p_compile.stdout.readline, ""):
                    if _ingest_cancelled:
                        p_compile.terminate()
                        log_callback("[Auto-Compile] Compilation cancelled by user.")
                        break
                    log_callback(f"[Compile] {line.strip()}")
                p_compile.wait()
                
                if p_compile.returncode == 0 and not _ingest_cancelled:
                    log_callback("[Auto-Compile] Wiki compilation finished successfully.")
                    
                    log_callback("\n[Auto-Index] Rebuilding search index...")
                    _ingest_status["progress_percent"] = 97
                    _save_status()
                    
                    p_index = subprocess.Popen(
                        [sys.executable, "scripts/build_index.py", "--rebuild"],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True,
                        bufsize=1,
                        encoding="utf-8",
                        errors="replace",
                        env={**os.environ, "PYTHONUTF8": "1"}
                    )
                    for line in iter(p_index.stdout.readline, ""):
                        if _ingest_cancelled:
                            p_index.terminate()
                            log_callback("[Auto-Index] Index building cancelled by user.")
                            break
                        log_callback(f"[Index] {line.strip()}")
                    p_index.wait()
                    if p_index.returncode == 0 and not _ingest_cancelled:
                        log_callback("[Auto-Index] Search index rebuilt successfully.")
                    else:
                        log_callback(f"[Auto-Index] Failed with exit code {p_index.returncode}")
                else:
                    log_callback(f"[Auto-Compile] Failed with exit code {p_compile.returncode}")
            
            _ingest_status["progress_percent"] = 100
        _save_status()
        print(f"[BACKGROUND TASK] arXiv ingestion completed! Total papers: {total_papers}")
    except Exception as e:
        error_msg = str(e)
        _ingest_status["error"] = error_msg
        _ingest_status["logs"].append(f"Error during ingestion: {error_msg}")
        _save_status()
        print(f"[BACKGROUND TASK] arXiv Ingestion Failed: {e}")
    finally:
        _ingest_running = False
        _ingest_status["running"] = False
        _save_status()

@router.post("/api/scripts/ingest")
async def trigger_ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    global _ingest_running
    if _ingest_running:
        raise HTTPException(status_code=409, detail="arXiv Ingestion is already running in the background.")
    
    _ingest_running = True
    # Ensure background task status reflects starting state immediately
    global _ingest_status
    _ingest_status["running"] = True
    _ingest_status["error"] = None
    _ingest_status["logs"].append("Triggering background task...")
    _save_status()
    
    background_tasks.add_task(_run_ingestion_sync, req)
    return {"status": "started", "message": "arXiv paper ingestion started in the background."}

@router.post("/api/scripts/ingest/stop")
async def stop_ingest():
    global _ingest_running, _ingest_cancelled, _ingest_status
    if not _ingest_running:
        return {"status": "ignored", "message": "No ingestion task is currently running."}
    
    _ingest_cancelled = True
    _ingest_status["logs"].append("Cancellation signal received. Halting ingestion...")
    _save_status()
    return {"status": "stopping", "message": "Stopping arXiv paper ingestion background task."}

@router.get("/api/scripts/ingest/status")
async def get_ingest_status():
    global _ingest_running, _ingest_status
    # Always keep running in sync
    _ingest_status["running"] = _ingest_running
    return _ingest_status

@router.post("/api/scripts/ingest/clear")
async def clear_ingest_status():
    global _ingest_status, _ingest_running
    if _ingest_running:
        raise HTTPException(status_code=400, detail="Cannot clear status while ingestion is running.")
    
    _ingest_status = {
        "running": False,
        "current_date": None,
        "dates_total": 0,
        "dates_processed": 0,
        "papers_fetched": 0,
        "logs": [],
        "error": None,
        "progress_percent": 0
    }
    _save_status()
    return {"status": "cleared", "message": "Ingestion status and logs cleared."}

# Migration task lock
_migration_running = False

def _run_migration_sync():
    global _migration_running
    try:
        print("[BACKGROUND TASK] Starting domain migration...")
        counts = migrate_existing_papers()
        print(f"[BACKGROUND TASK] Domain migration complete: {counts}")
    except Exception as e:
        print(f"[BACKGROUND TASK] Domain migration failed: {e}")
    finally:
        _migration_running = False

@router.post("/api/scripts/migrate")
async def trigger_migrate(background_tasks: BackgroundTasks):
    global _migration_running
    if _migration_running:
        raise HTTPException(status_code=409, detail="Domain storage migration is already running.")
    
    _migration_running = True
    background_tasks.add_task(_run_migration_sync)
    return {"status": "started", "message": "Domain storage migration started in the background."}

@router.get("/api/scripts/migrate/status")
async def get_migration_status():
    global _migration_running
    return {"running": _migration_running}


# ─────────────────────────────────────────────────────────────────────────
# Compilation and Indexing Manual Scripts Background Tasks
# ─────────────────────────────────────────────────────────────────────────

_compile_running = False
_compile_cancelled = False
_compile_status = {
    "running": False,
    "logs": [],
    "error": None
}

_index_running = False
_index_status = {
    "running": False,
    "logs": [],
    "error": None
}

def _run_compile_sync():
    global _compile_running, _compile_status, _compile_cancelled
    _compile_cancelled = False
    _compile_status = {
        "running": True,
        "logs": ["Starting manual wiki compilation..."],
        "error": None
    }
    try:
        import subprocess
        p_compile = subprocess.Popen(
            [sys.executable, "scripts/compile_wiki.py", "--all"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1"}
        )
        for line in iter(p_compile.stdout.readline, ""):
            if _compile_cancelled:
                p_compile.terminate()
                _compile_status["logs"].append("Compilation cancelled by user.")
                break
            _compile_status["logs"].append(line.strip())
        p_compile.wait()
        if p_compile.returncode == 0 and not _compile_cancelled:
            _compile_status["logs"].append("Manual wiki compilation completed successfully.")
        elif not _compile_cancelled:
            _compile_status["logs"].append(f"Compilation failed with exit code {p_compile.returncode}")
    except Exception as e:
        _compile_status["error"] = str(e)
        _compile_status["logs"].append(f"Error during compilation: {e}")
    finally:
        _compile_running = False
        _compile_status["running"] = False

def _run_index_sync(rebuild: bool):
    global _index_running, _index_status
    _index_status = {
        "running": True,
        "logs": ["Starting manual search index build..."],
        "error": None
    }
    try:
        import subprocess
        args = [sys.executable, "scripts/build_index.py"]
        if rebuild:
            args.append("--rebuild")
            
        p_index = subprocess.Popen(
            args,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
            encoding="utf-8",
            errors="replace",
            env={**os.environ, "PYTHONUTF8": "1"}
        )
        for line in iter(p_index.stdout.readline, ""):
            _index_status["logs"].append(line.strip())
        p_index.wait()
        if p_index.returncode == 0:
            _index_status["logs"].append("Manual search index build completed successfully.")
        else:
            _index_status["logs"].append(f"Indexing failed with exit code {p_index.returncode}")
    except Exception as e:
        _index_status["error"] = str(e)
        _index_status["logs"].append(f"Error during indexing: {e}")
    finally:
        _index_running = False
        _index_status["running"] = False

class CompileRequest(BaseModel):
    rebuild_wiki: bool = Field(True, description="Rebuild concept pages and index after compilation.")

class IndexRequest(BaseModel):
    rebuild: bool = Field(True, description="Delete and rebuild index from scratch.")

@router.post("/api/scripts/compile")
async def trigger_compile(req: CompileRequest, background_tasks: BackgroundTasks):
    global _compile_running
    if _compile_running:
        raise HTTPException(status_code=409, detail="Wiki compilation is already running.")
    _compile_running = True
    background_tasks.add_task(_run_compile_sync)
    return {"status": "started", "message": "Wiki compilation started in the background."}

@router.get("/api/scripts/compile/status")
async def get_compile_status():
    global _compile_running, _compile_status
    _compile_status["running"] = _compile_running
    return _compile_status

@router.post("/api/scripts/compile/stop")
async def stop_compile():
    global _compile_cancelled, _compile_running
    if not _compile_running:
        return {"status": "ignored", "message": "No compilation task is currently running."}
    _compile_cancelled = True
    return {"status": "stopping", "message": "Stopping wiki compilation task."}

@router.post("/api/scripts/compile/clear")
async def clear_compile_status():
    global _compile_status, _compile_running
    if _compile_running:
        raise HTTPException(status_code=400, detail="Cannot clear status while compilation is running.")
    _compile_status = {
        "running": False,
        "logs": [],
        "error": None
    }
    return {"status": "cleared", "message": "Compilation status and logs cleared."}

@router.post("/api/scripts/index")
async def trigger_index(req: IndexRequest, background_tasks: BackgroundTasks):
    global _index_running
    if _index_running:
        raise HTTPException(status_code=409, detail="Search index build is already running.")
    _index_running = True
    background_tasks.add_task(_run_index_sync, req.rebuild)
    return {"status": "started", "message": "Search index build started in the background."}

@router.get("/api/scripts/index/status")
async def get_index_status():
    global _index_running, _index_status
    _index_status["running"] = _index_running
    return _index_status

@router.post("/api/scripts/index/clear")
async def clear_index_status():
    global _index_status, _index_running
    if _index_running:
        raise HTTPException(status_code=400, detail="Cannot clear status while indexing is running.")
    _index_status = {
        "running": False,
        "logs": [],
        "error": None
    }
    return {"status": "cleared", "message": "Indexing status and logs cleared."}
