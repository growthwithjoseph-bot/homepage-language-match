"""FastAPI application for Topic Coverage.

M0 ships the skeleton: the app boots, the SQLite schema is created on startup,
and `GET /health` returns 200. Run + map endpoints (SPEC §8) arrive in M5.
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import config
from .db import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Ensure storage + schema exist before serving any request.
    config.ensure_dirs()
    init_db()
    yield


app = FastAPI(title="Topic Coverage", version="0.1.0", lifespan=lifespan)


@app.get("/health")
def health():
    return {"status": "ok"}
