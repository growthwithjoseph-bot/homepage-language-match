"""Run orchestration — homepage language-similarity comparison.

A run fetches every domain's homepage, extracts its headlines + paragraphs, and
scores each competitor's similarity to the own domain (semantic + lexical) with
an LLM "why". Runs execute in a background thread (see app.py); poll the run
status, then read GET /runs/{id}/report.
"""
from __future__ import annotations

import json
from typing import List, Optional

from ..config import Config, config
from ..db import get_connection, init_db, store_homepage, store_similarity
from .explain import explain_with_source
from .fetch import fetch_all
from .homepage import extract_homepage, normalize_base
from .scoring import build_profile, score


# --- run/domain records -----------------------------------------------------

def create_run(
    own_domain: str,
    competitor_domains: List[str],
    market_language: str,
    cfg: Config = config,
) -> int:
    """Create a run row + its domain rows (own first). Returns the run id."""
    init_db(cfg.db_path)
    conn = get_connection(cfg.db_path)
    try:
        cur = conn.execute(
            "INSERT INTO runs (own_domain, competitor_domains_json, market_language, "
            "max_pages, status) VALUES (?, ?, ?, 0, 'running')",
            (own_domain, json.dumps(competitor_domains), market_language),
        )
        run_id = cur.lastrowid
        conn.execute("INSERT INTO domains (run_id, domain, is_own) VALUES (?, ?, 1)",
                     (run_id, own_domain))
        for comp in competitor_domains:
            conn.execute("INSERT INTO domains (run_id, domain, is_own) VALUES (?, ?, 0)",
                         (run_id, comp))
        conn.commit()
        return run_id
    finally:
        conn.close()


def set_run_status(run_id: int, status: str, cfg: Config = config) -> None:
    conn = get_connection(cfg.db_path)
    try:
        if status in ("done", "error"):
            conn.execute("UPDATE runs SET status=?, finished_at=datetime('now') WHERE id=?",
                         (status, run_id))
        else:
            conn.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))
        conn.commit()
    finally:
        conn.close()


def get_run(run_id: int, cfg: Config = config):
    conn = get_connection(cfg.db_path)
    try:
        return conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    finally:
        conn.close()


def get_domains(run_id: int, cfg: Config = config):
    conn = get_connection(cfg.db_path)
    try:
        return conn.execute(
            "SELECT id, domain, is_own FROM domains WHERE run_id=? ORDER BY is_own DESC, id",
            (run_id,),
        ).fetchall()
    finally:
        conn.close()


# --- the comparison ---------------------------------------------------------

def _fetch_homepages(domains, cfg: Config) -> dict:
    """Fetch each domain's homepage (one request each, run concurrently) and
    extract its headlines + paragraphs. Returns {domain_id: HomepageContent}."""
    urls = {d["id"]: normalize_base(d["domain"]) for d in domains}
    got = {}
    fetch_all(list(dict.fromkeys(urls.values())), cfg=cfg,
              on_result=lambda r: got.__setitem__(r.url, r))
    return {
        d["id"]: extract_homepage(
            (got.get(urls[d["id"]]).html if got.get(urls[d["id"]]) is not None else ""),
            urls[d["id"]],
        )
        for d in domains
    }


def execute_run(run_id: int, cfg: Config = config) -> int:
    """Fetch every homepage, extract headlines + paragraphs, and score each
    competitor's language similarity to the own domain, with an LLM 'why'."""
    run = get_run(run_id, cfg=cfg)
    if run is None:
        raise ValueError(f"run {run_id} not found")
    set_run_status(run_id, "running", cfg=cfg)
    try:
        domains = get_domains(run_id, cfg=cfg)          # own domain first
        own = next((d for d in domains if d["is_own"]), None)
        if own is None:
            raise ValueError("run has no own domain")

        contents = _fetch_homepages(domains, cfg)
        for d in domains:
            store_homepage(d["id"], contents[d["id"]], db_path=cfg.db_path)

        profiles = {did: build_profile(c, cfg) for did, c in contents.items()}
        own_profile = profiles[own["id"]]
        own_name = normalize_base(own["domain"]).split("//")[-1]
        for d in domains:
            if d["is_own"]:
                continue
            s = score(own_profile, profiles[d["id"]], cfg)
            comp_name = normalize_base(d["domain"]).split("//")[-1]
            why, used_ai = explain_with_source(own_name, comp_name, contents[own["id"]],
                                               contents[d["id"]], s, cfg)
            store_similarity(run_id, d["id"], s, explanation=why,
                             explanation_ai=used_ai, db_path=cfg.db_path)
            print(f"  [{d['domain']}] scored + explained")
        set_run_status(run_id, "done", cfg=cfg)
    except Exception:
        set_run_status(run_id, "error", cfg=cfg)
        raise
    return run_id


def run_pipeline(own_domain: str, competitor_domains: List[str],
                 market_language: Optional[str] = None, cfg: Config = config) -> int:
    """Create a run and execute it synchronously (used by the API + tests)."""
    lang = market_language or cfg.default_market_language
    run_id = create_run(own_domain, competitor_domains, lang, cfg=cfg)
    return execute_run(run_id, cfg=cfg)
