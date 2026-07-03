"""FastAPI application for Topic Coverage (SPEC §8).

Endpoints:
  GET  /health
  POST /runs                     start an analysis (runs in the background)
  GET  /runs/{id}                status + counts
  GET  /runs/{id}/map            the category→topic coverage tree
  GET  /runs/{id}/topics/{tid}   per-topic detected content

A run executes in a background thread so POST returns immediately with a
run_id (SPEC §8: returns {run_id, status:"running"}). The pipeline is otherwise
synchronous; poll GET /runs/{id} for progress.
"""
from __future__ import annotations

import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import config
from .db import (
    build_report,
    fail_orphaned_runs,
    get_connection,
    init_db,
    list_runs,
)
from .pipeline.run import create_run, execute_run

ROOT_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT_DIR / "frontend"


@asynccontextmanager
async def lifespan(app: FastAPI):
    config.ensure_dirs()
    init_db()
    # A restart kills any in-flight run's worker thread; fail those so the UI
    # doesn't poll them forever (they can't be resumed).
    orphaned = fail_orphaned_runs()
    if orphaned:
        print(f"  marked {orphaned} interrupted run(s) as error on startup")
    yield


app = FastAPI(title="Topic Coverage", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- schemas ----------------------------------------------------------------

class RunRequest(BaseModel):
    own_domain: str
    competitor_domains: List[str] = Field(default_factory=list)
    market_language: Optional[str] = None


# --- background execution ---------------------------------------------------

def _run_in_background(run_id: int) -> None:
    def worker():
        try:
            execute_run(run_id)
        except Exception as exc:  # status is already set to 'error' inside
            print(f"[run {run_id}] failed: {exc}")

    threading.Thread(target=worker, daemon=True).start()


# --- routes -----------------------------------------------------------------

@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/runs")
def list_runs_endpoint():
    """Search history — recent comparisons, newest first."""
    return {"runs": list_runs()}


@app.post("/runs")
def start_run(req: RunRequest):
    lang = req.market_language or config.default_market_language
    # Cap the number of competitors (product rule; also a defensive guard).
    competitors = (req.competitor_domains or [])[: config.max_competitors]
    run_id = create_run(req.own_domain, competitors, lang)
    _run_in_background(run_id)
    return {"run_id": run_id, "status": "running"}


@app.get("/runs/{run_id}")
def run_status(run_id: int):
    """Run status (the UI polls this until 'done', then reads /report)."""
    conn = get_connection()
    try:
        run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if run is None:
            raise HTTPException(404, "run not found")
    finally:
        conn.close()
    return {
        "run_id": run_id,
        "status": run["status"],
        "own_domain": run["own_domain"],
        "created_at": run["created_at"],
        "finished_at": run["finished_at"],
    }


@app.get("/runs/{run_id}/report")
def run_report(run_id: int):
    """Homepage language-similarity report: own domain + per-competitor scores."""
    data = build_report(run_id)
    if data is None:
        raise HTTPException(404, "run not found")
    return data


# --- static frontend --------------------------------------------------------
# Served last so it doesn't shadow the API routes above.
class _NoCacheStatic(StaticFiles):
    """StaticFiles that tells the browser to always revalidate. Without this the
    browser heuristically caches app.js/index.html, so edits don't show until a
    hard refresh — a recurring source of "the change isn't there" confusion.
    (no-cache still allows fast 304s via ETag when the file is unchanged.)"""

    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-cache"
        return resp


if FRONTEND_DIR.exists():
    app.mount("/", _NoCacheStatic(directory=str(FRONTEND_DIR), html=True), name="frontend")
