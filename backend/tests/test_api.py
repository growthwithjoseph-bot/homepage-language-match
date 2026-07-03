"""Compare API: create (with competitor cap), status, report, history."""
from fastapi.testclient import TestClient

from backend import app as app_module
from backend.config import config
from backend.db import get_connection, init_db, store_homepage, store_similarity
from backend.pipeline.homepage import HomepageContent
from backend.pipeline.run import create_run
from backend.pipeline.scoring import SimilarityScores

client = TestClient(app_module.app)


def test_post_runs_returns_running_and_caps_competitors(monkeypatch):
    monkeypatch.setattr(app_module, "_run_in_background", lambda run_id: None)
    resp = client.post("/runs", json={
        "own_domain": "you.com",
        "competitor_domains": [f"c{i}.com" for i in range(7)],  # 7 -> capped
    })
    assert resp.status_code == 200 and resp.json()["status"] == "running"
    conn = get_connection()
    try:
        n = conn.execute("SELECT COUNT(*) FROM domains WHERE run_id=? AND is_own=0",
                         (resp.json()["run_id"],)).fetchone()[0]
    finally:
        conn.close()
    assert n == config.max_competitors      # capped to 5


def _seed_compare_run():
    init_db(config.db_path)
    rid = create_run("you.com", ["rival.com"], "en")
    conn = get_connection()
    try:
        doms = {r["domain"]: r["id"]
                for r in conn.execute("SELECT id, domain FROM domains WHERE run_id=?", (rid,))}
    finally:
        conn.close()
    store_homepage(doms["you.com"], HomepageContent(
        "https://you.com", title="You", headlines=["AI notetaker"],
        paragraphs=["We take notes with AI for you."]))
    store_homepage(doms["rival.com"], HomepageContent(
        "https://rival.com", title="Rival", headlines=["AI notetaker"],
        paragraphs=["Rival takes notes with AI."]))
    store_similarity(rid, doms["rival.com"],
                     SimilarityScores(90.0, 50.0, 88.0, 40.0, ["ai notetaker"], []),
                     explanation="They are similar.", explanation_ai=True)
    conn = get_connection()
    try:
        conn.execute("UPDATE runs SET status='done' WHERE id=?", (rid,))
        conn.commit()
    finally:
        conn.close()
    return rid


def test_report_status_and_history():
    rid = _seed_compare_run()

    rep = client.get(f"/runs/{rid}/report").json()
    assert rep["own"]["domain"] == "you.com"
    comp = rep["competitors"][0]
    assert comp["domain"] == "rival.com"
    assert comp["scores"]["headline_semantic"] == 90.0
    assert comp["explanation_ai"] is True
    assert comp["headlines"] == ["AI notetaker"]        # extracted text is returned

    st = client.get(f"/runs/{rid}").json()
    assert st["status"] == "done" and st["own_domain"] == "you.com"

    runs = client.get("/runs").json()["runs"]
    assert any(r["run_id"] == rid for r in runs)         # shows in history


def test_missing_run_404():
    assert client.get("/runs/999999/report").status_code == 404
    assert client.get("/runs/999999").status_code == 404
