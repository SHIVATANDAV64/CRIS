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

# Simple lock to prevent running concurrent ingestion tasks
_ingest_running = False

def _run_ingestion_sync(req: IngestRequest):
    global _ingest_running
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

        # Parse categories
        categories_list = [c.strip() for c in req.categories.split(",") if c.strip()] if req.categories else None

        print(f"[BACKGROUND TASK] Starting arXiv ingestion for dates: {dates}")
        total_papers = 0
        for date_str in dates:
            print(f"[BACKGROUND TASK] Fetching for date: {date_str}")
            papers = fetch_papers(
                from_date=date_str,
                categories=categories_list,
                max_papers=req.max_papers
            )
            if papers:
                if req.domain_mode:
                    save_papers_by_domain(papers)
                else:
                    save_papers(papers, date_str)
                total_papers += len(papers)
        print(f"[BACKGROUND TASK] arXiv ingestion completed! Total papers: {total_papers}")
    except Exception as e:
        print(f"[BACKGROUND TASK] arXiv Ingestion Failed: {e}")
    finally:
        _ingest_running = False

@router.post("/api/scripts/ingest")
async def trigger_ingest(req: IngestRequest, background_tasks: BackgroundTasks):
    global _ingest_running
    if _ingest_running:
        raise HTTPException(status_code=409, detail="arXiv Ingestion is already running in the background.")
    
    _ingest_running = True
    background_tasks.add_task(_run_ingestion_sync, req)
    return {"status": "started", "message": "arXiv paper ingestion started in the background."}

@router.get("/api/scripts/ingest/status")
async def get_ingest_status():
    global _ingest_running
    return {"running": _ingest_running}

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
