"""SQLite storage for Topic Coverage.

Schema follows SPEC §7. Embeddings are stored as raw float32 blobs and cosine
similarity is done in numpy at read time (fine at this scale — SPEC §7 allows
either this or the sqlite-vec extension).
"""
from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Optional

import numpy as np

from .config import config

SCHEMA = """
PRAGMA journal_mode = WAL;
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS runs (
    id                       INTEGER PRIMARY KEY AUTOINCREMENT,
    own_domain               TEXT    NOT NULL,
    competitor_domains_json  TEXT    NOT NULL,
    market_language          TEXT    NOT NULL DEFAULT 'en',
    max_pages                INTEGER NOT NULL,
    status                   TEXT    NOT NULL DEFAULT 'pending',
    created_at               TEXT    NOT NULL DEFAULT (datetime('now')),
    finished_at              TEXT
);

CREATE TABLE IF NOT EXISTS domains (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id    INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    domain    TEXT    NOT NULL,
    is_own    INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS pages (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    domain_id   INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    url         TEXT    NOT NULL,
    title       TEXT,
    text        TEXT,
    lang        TEXT,
    etag        TEXT,
    fetched_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS chunks (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    page_id    INTEGER NOT NULL REFERENCES pages(id) ON DELETE CASCADE,
    domain_id  INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    run_id     INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    text       TEXT    NOT NULL,
    embedding  BLOB,
    topic_id   INTEGER REFERENCES topics(id) ON DELETE SET NULL
);

CREATE TABLE IF NOT EXISTS categories (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id  INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    label   TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS topics (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id              INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    category_id         INTEGER REFERENCES categories(id) ON DELETE SET NULL,
    label               TEXT    NOT NULL,
    centroid            BLOB,
    rep_chunk_ids_json  TEXT
);

CREATE TABLE IF NOT EXISTS topic_coverage (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id      INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    topic_id    INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    domain_id   INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
    strength    REAL    NOT NULL DEFAULT 0,
    page_count  INTEGER NOT NULL DEFAULT 0,
    covered     INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS topic_state (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id           INTEGER NOT NULL REFERENCES runs(id) ON DELETE CASCADE,
    topic_id         INTEGER NOT NULL REFERENCES topics(id) ON DELETE CASCADE,
    state            TEXT    NOT NULL,
    you_pct          INTEGER NOT NULL DEFAULT 0,
    competitors_pct  INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_pages_domain   ON pages(domain_id);
CREATE INDEX IF NOT EXISTS idx_chunks_run     ON chunks(run_id);
CREATE INDEX IF NOT EXISTS idx_chunks_domain  ON chunks(domain_id);
CREATE INDEX IF NOT EXISTS idx_chunks_topic   ON chunks(topic_id);
CREATE INDEX IF NOT EXISTS idx_topics_run     ON topics(run_id);
CREATE INDEX IF NOT EXISTS idx_cov_run        ON topic_coverage(run_id);
CREATE INDEX IF NOT EXISTS idx_state_run      ON topic_state(run_id);
"""

# Tables we expect to exist after init — used by the M0 acceptance check.
EXPECTED_TABLES = [
    "runs",
    "domains",
    "pages",
    "chunks",
    "categories",
    "topics",
    "topic_coverage",
    "topic_state",
]


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
        conn.commit()
    finally:
        conn.close()
    return path


def list_tables(conn: sqlite3.Connection) -> Iterable[str]:
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


# --- embedding (de)serialisation -------------------------------------------

def embedding_to_blob(vec) -> bytes:
    """Pack a vector to a float32 blob for storage."""
    return np.asarray(vec, dtype=np.float32).tobytes()


def blob_to_embedding(blob: Optional[bytes]) -> Optional[np.ndarray]:
    """Unpack a float32 blob back to a numpy vector (None passes through)."""
    if blob is None:
        return None
    return np.frombuffer(blob, dtype=np.float32)


if __name__ == "__main__":  # `python -m backend.db` initialises the DB
    p = init_db()
    print(f"Initialised DB at {p}")
