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
        "error": None
    }
    if STATUS_FILE.exists():
        try:
            with open(STATUS_FILE, "r") as f:
                data = json.load(f)
                data["running"] = False  # If the server is restarting/starting, it cannot be running
                return data
        except Exception:
            pass
    return default_status

def _save_status():
    global _ingest_status
    try:
        STATUS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(STATUS_FILE, "w") as f:
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
        "error": None
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
                is_cancelled=lambda: _ingest_cancelled
            )

            if _ingest_cancelled:
                _ingest_status["logs"].append("Ingestion task stopped by user.")
                _save_status()
                break

            if papers:
                _ingest_status["logs"].append(f"Saving {len(papers)} papers fetched for {date_str}...")
                _save_status()
                if req.domain_mode:
                    save_papers_by_domain(papers)
                else:
                    save_papers(papers, date_str)
                total_papers += len(papers)
                _ingest_status["papers_fetched"] = total_papers
            else:
                _ingest_status["logs"].append(f"No papers found for {date_str}.")
            
            _ingest_status["dates_processed"] = idx + 1
            _save_status()

        if _ingest_cancelled:
            _ingest_status["logs"].append("Ingestion aborted by user.")
        else:
            _ingest_status["logs"].append(f"Ingestion completed successfully! Total papers added to library: {total_papers}")
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
