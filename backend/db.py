"""SQLite storage for the homepage-compare tool.

Tables: runs, domains, homepages (extracted headlines/paragraphs per domain),
and similarity (per-competitor sub-scores + evidence + explanation).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

from .config import config

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    own_domain               TEXT    NOT NULL,
    competitor_domains_json  TEXT    NOT NULL,
    market_language          TEXT    NOT NULL DEFAULT 'en',
    max_pages                INTEGER NOT NULL DEFAULT 0,
    status                   TEXT    NOT NULL DEFAULT 'pending',
    created_at               TEXT    NOT NULL DEFAULT (datetime('now')),
    finished_at              TEXT
);

CREATE TABLE IF NOT EXISTS domains (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    domain  TEXT    NOT NULL,
    is_own  INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS homepages (
    domain_id   INTEGER PRIMARY KEY REFERENCES domains(id) ON DELETE CASCADE,
    url         TEXT,
    title       TEXT,
    headlines   TEXT,   -- JSON array of headline strings
    paragraphs  TEXT,   -- JSON array of paragraph strings
    fetched_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS similarity (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id            INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    domain_id         INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,  -- the competitor
    h_semantic        REAL,
    h_lexical         REAL,
    p_semantic        REAL,
    p_lexical         REAL,
    shared_headlines  TEXT,   -- JSON array
    shared_paragraphs TEXT,   -- JSON array
    explanation       TEXT,
    explanation_ai    INTEGER NOT NULL DEFAULT 0   -- 1 = LLM, 0 = deterministic fallback
);

CREATE INDEX IF NOT EXISTS idx_domains_run ON domains(run_id);
CREATE INDEX IF NOT EXISTS idx_sim_run     ON similarity(run_id);
"""

# Tables we expect to exist after init.
EXPECTED_TABLES = ["runs", "domains", "homepages", "similarity"]


def get_connection(db_path: Optional[Path] = None) -> sqlite3.Connection:
    """Open a connection with sensible defaults (row access by name, FKs on)."""
    path = Path(db_path) if db_path is not None else config.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def init_db(db_path: Optional[Path] = None) -> Path:
    """Create the schema if it doesn't exist. Returns the DB path."""
    path = Path(db_path) if db_path is not None else config.db_path
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection(path)
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        conn.commit()
    finally:
        conn.close()
    return path


def _migrate(conn: sqlite3.Connection) -> None:
    """Additive migrations for databases created before a column existed
    (`CREATE TABLE IF NOT EXISTS` never alters an existing table)."""
    sim_cols = {r["name"] for r in conn.execute("PRAGMA table_info(similarity)")}
    if sim_cols and "explanation_ai" not in sim_cols:
        conn.execute("ALTER TABLE similarity ADD COLUMN explanation_ai INTEGER NOT NULL DEFAULT 0")


# Statuses a run can rest in permanently. Anything else means a worker was
# mid-flight; if the process is gone (e.g. server restart) the run is orphaned.
TERMINAL_STATUSES = ("done", "error", "cancelled")


def fail_orphaned_runs(db_path: Optional[Path] = None) -> int:
    """Mark any non-terminal run as 'error'. Runs execute in a background thread,
    so a server restart leaves in-flight runs stuck at 'running' forever with no
    worker. Called on startup so the UI stops polling dead runs. Returns count."""
    conn = get_connection(db_path)
    try:
        placeholders = ",".join("?" * len(TERMINAL_STATUSES))
        cur = conn.execute(
            f"UPDATE runs SET status='error', finished_at=datetime('now') "
            f"WHERE status NOT IN ({placeholders})",
            TERMINAL_STATUSES,
        )
        conn.commit()
        return cur.rowcount
    finally:
        conn.close()


def list_tables(conn: sqlite3.Connection) -> Iterable[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


import json as _json

# --- homepage-compare storage + report -------------------------------------

def list_runs(limit: int = 100, db_path: Optional[Path] = None) -> list:
    """Recent comparisons, newest first — for the search history."""
    conn = get_connection(db_path)
    try:
        # Only homepage-compare runs (those that stored homepages) — excludes any
        # legacy runs so a history click always loads a real report.
        rows = conn.execute(
            "SELECT id, own_domain, competitor_domains_json, status, created_at "
            "FROM runs WHERE id IN "
            "(SELECT d.run_id FROM domains d JOIN homepages h ON h.domain_id = d.id) "
            "ORDER BY id DESC LIMIT ?", (limit,),
        ).fetchall()
        out = []
        for r in rows:
            try:
                comps = _json.loads(r["competitor_domains_json"] or "[]")
            except Exception:
                comps = []
            out.append({
                "run_id": r["id"], "own_domain": r["own_domain"],
                "competitors": comps, "competitor_count": len(comps),
                "status": r["status"], "created_at": r["created_at"],
            })
        return out
    finally:
        conn.close()

def store_homepage(domain_id: int, content, db_path: Optional[Path] = None) -> None:
    """Save a domain's extracted homepage (headlines + paragraphs)."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO homepages (domain_id, url, title, headlines, paragraphs) "
            "VALUES (?, ?, ?, ?, ?) "
            "ON CONFLICT(domain_id) DO UPDATE SET url=excluded.url, title=excluded.title, "
            "headlines=excluded.headlines, paragraphs=excluded.paragraphs",
            (domain_id, content.url, content.title,
             _json.dumps(content.headlines), _json.dumps(content.paragraphs)),
        )
        conn.commit()
    finally:
        conn.close()


def store_similarity(run_id: int, domain_id: int, scores,
                     explanation: Optional[str] = None,
                     explanation_ai: bool = False,
                     db_path: Optional[Path] = None) -> None:
    """Save one competitor's similarity sub-scores + lexical evidence."""
    conn = get_connection(db_path)
    try:
        conn.execute(
            "INSERT INTO similarity (run_id, domain_id, h_semantic, h_lexical, "
            "p_semantic, p_lexical, shared_headlines, shared_paragraphs, explanation, "
            "explanation_ai) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (run_id, domain_id, scores.headline_semantic, scores.headline_lexical,
             scores.paragraph_semantic, scores.paragraph_lexical,
             _json.dumps(scores.shared_headline_phrases),
             _json.dumps(scores.shared_paragraph_phrases), explanation,
             1 if explanation_ai else 0),
        )
        conn.commit()
    finally:
        conn.close()


def build_report(run_id: int, db_path: Optional[Path] = None) -> Optional[dict]:
    """Assemble the homepage-comparison report: own domain + per-competitor
    sub-scores, lexical evidence, and explanation (SPEC: the compare tool)."""
    conn = get_connection(db_path)
    try:
        run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        if run is None:
            return None
        doms = conn.execute(
            "SELECT id, domain, is_own FROM domains WHERE run_id=? ORDER BY is_own DESC, id",
            (run_id,),
        ).fetchall()

        def homepage_meta(domain_id):
            hp = conn.execute(
                "SELECT title, headlines, paragraphs FROM homepages WHERE domain_id=?",
                (domain_id,),
            ).fetchone()
            if hp is None:
                return {"title": "", "headlines": [], "paragraphs": [],
                        "headline_count": 0, "paragraph_count": 0}
            headlines = _json.loads(hp["headlines"] or "[]")
            paragraphs = _json.loads(hp["paragraphs"] or "[]")
            return {
                "title": hp["title"] or "",
                "headlines": headlines, "paragraphs": paragraphs,
                "headline_count": len(headlines), "paragraph_count": len(paragraphs),
            }

        own_row = next((d for d in doms if d["is_own"]), None)
        own = None
        if own_row is not None:
            own = {"domain": own_row["domain"], **homepage_meta(own_row["id"])}

        competitors = []
        for d in doms:
            if d["is_own"]:
                continue
            sim = conn.execute(
                "SELECT * FROM similarity WHERE run_id=? AND domain_id=?",
                (run_id, d["id"]),
            ).fetchone()
            entry = {"domain": d["domain"], **homepage_meta(d["id"])}
            entry["scores"] = {
                "headline_semantic": sim["h_semantic"] if sim else None,
                "headline_lexical": sim["h_lexical"] if sim else None,
                "paragraph_semantic": sim["p_semantic"] if sim else None,
                "paragraph_lexical": sim["p_lexical"] if sim else None,
            }
            entry["shared_headlines"] = _json.loads(sim["shared_headlines"]) if sim and sim["shared_headlines"] else []
            entry["shared_paragraphs"] = _json.loads(sim["shared_paragraphs"]) if sim and sim["shared_paragraphs"] else []
            entry["explanation"] = sim["explanation"] if sim else None
            entry["explanation_ai"] = bool(sim["explanation_ai"]) if sim else False
            competitors.append(entry)

        return {
            "run_id": run_id,
            "status": run["status"],
            "own": own,
            "competitors": competitors,
        }
    finally:
        conn.close()
