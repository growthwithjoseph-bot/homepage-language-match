"""M0 acceptance: the app boots, /health is 200, and the DB has all tables."""
from pathlib import Path

from fastapi.testclient import TestClient

from backend.app import app
from backend.db import EXPECTED_TABLES, get_connection, init_db, list_tables


def test_health_ok():
    with TestClient(app) as client:  # triggers lifespan (init_db)
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json() == {"status": "ok"}


def test_db_has_all_tables(tmp_path: Path):
    db = tmp_path / "test.db"
    init_db(db)
    assert db.exists()
    conn = get_connection(db)
    try:
        tables = set(list_tables(conn))
    finally:
        conn.close()
    missing = set(EXPECTED_TABLES) - tables
    assert not missing, f"missing tables: {missing}"
