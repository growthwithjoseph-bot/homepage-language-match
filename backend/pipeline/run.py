"""Run orchestration (SPEC §5).

For M1 this stores runs/domains and crawls one domain into `pages`. Later
milestones extend `run_pipeline` to chunk/embed (M2), discover topics (M3) and
score coverage (M4). The CLI (`make crawl DOMAIN=...`) exercises just the crawl.
"""
from __future__ import annotations

import json
import time
from typing import List, Optional

from ..config import Config, config
from ..db import get_connection, init_db
from .chunk_embed import embed_run
from .coverage import score_coverage
from .discover import (
    build_exclude_regex,
    discover_urls,
    extract_links,
    normalize_base,
    registrable_host,
)
from .extract import extract_page
from .fetch import fetch_all
from .topics import discover_topics


# --- DB write helpers -------------------------------------------------------

def create_run(
    own_domain: str,
    competitor_domains: List[str],
    market_language: str,
    max_pages: int,
    cfg: Config = config,
) -> int:
    init_db(cfg.db_path)
    conn = get_connection(cfg.db_path)
    try:
        cur = conn.execute(
            """INSERT INTO runs
               (own_domain, competitor_domains_json, market_language, max_pages, status)
               VALUES (?, ?, ?, ?, 'running')""",
            (own_domain, json.dumps(competitor_domains), market_language, max_pages),
        )
        run_id = cur.lastrowid
        conn.execute(
            "INSERT INTO domains (run_id, domain, is_own) VALUES (?, ?, 1)",
            (run_id, own_domain),
        )
        for comp in competitor_domains:
            conn.execute(
                "INSERT INTO domains (run_id, domain, is_own) VALUES (?, ?, 0)",
                (run_id, comp),
            )
        conn.commit()
        return run_id
    finally:
        conn.close()


def set_run_status(run_id: int, status: str, cfg: Config = config) -> None:
    conn = get_connection(cfg.db_path)
    try:
        if status in ("done", "error"):
            conn.execute(
                "UPDATE runs SET status=?, finished_at=datetime('now') WHERE id=?",
                (status, run_id),
            )
        else:
            conn.execute("UPDATE runs SET status=? WHERE id=?", (status, run_id))
        conn.commit()
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


def _store_pages(domain_id: int, pages, cfg: Config) -> int:
    conn = get_connection(cfg.db_path)
    try:
        n = 0
        for pg in pages:
            conn.execute(
                """INSERT INTO pages (domain_id, url, title, text, lang, etag)
                   VALUES (?, ?, ?, ?, ?, ?)""",
                (domain_id, pg["url"], pg["title"], pg["text"], pg["lang"], pg.get("etag")),
            )
            n += 1
        conn.commit()
        return n
    finally:
        conn.close()


# --- M1 crawl ---------------------------------------------------------------

def crawl_domain(
    domain_id: int,
    domain: str,
    market_language: str,
    max_pages: Optional[int] = None,
    cfg: Config = config,
    seed: Optional[List[str]] = None,
) -> int:
    """Fetch → extract → store pages for one domain. Returns count.

    `seed` is the discovered URL list (see discover_urls); when omitted we
    discover here. From the seed we harvest on-domain links from fetched pages
    and follow new ones (cfg.link_augment_rounds hops) so pages a sitemap omits
    — or a site with no sitemap — are still found. Pages are stored incrementally
    for live progress. Bounded by max_pages and the time budget.
    """
    base = normalize_base(domain)
    base_host = registrable_host(base)
    exclude_re = build_exclude_regex(cfg.exclude_url_patterns)

    if max_pages is None:
        cap = cfg.max_pages_per_domain
    elif max_pages <= 0:
        cap = 1_000_000  # "all" (bounded by the time budget)
    else:
        cap = max_pages

    if seed is None:
        seed = discover_urls(domain, max_pages=max_pages, cfg=cfg)
    seen = set(seed)          # every URL queued (across rounds)
    frontier = list(seed)     # URLs to fetch this round
    harvested = set()         # on-domain links seen in fetched HTML

    # Time budget is a stall-guard, not a coverage cap — sized to the page cap.
    start = time.monotonic()
    total_budget = cfg.crawl_deadline_for(cap)

    def remaining():
        return None if total_budget is None else total_budget - (time.monotonic() - start)

    conn = get_connection(cfg.db_path)
    stored = {"n": 0}

    def record_discovered():
        conn.execute("UPDATE domains SET discovered=? WHERE id=?",
                     (min(len(seen), cap), domain_id))
        conn.commit()

    def handle(res):
        if not res.html:
            return
        page = extract_page(res.html, res.url, market_language=market_language)
        if page is not None:
            conn.execute(
                "INSERT INTO pages (domain_id, url, title, text, lang, etag) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (domain_id, page.url, page.title, page.text, page.lang, res.etag),
            )
            conn.commit()
            stored["n"] += 1
        # Harvest links even from pages we don't store (nav/index pages are often
        # thin but link to real content). res.html may be JS-rendered when the
        # static body was too thin (see fetch._maybe_render), so this also reaches
        # links on sitemap-less SPA sites when Playwright is installed.
        if cfg.link_augment_rounds > 0:
            harvested.update(extract_links(res.html, res.url, base_host, exclude_re))

    try:
        round_i = 0
        while frontier:
            record_discovered()
            rem = remaining()
            if rem is not None and rem <= 0:
                break
            fetch_all(frontier, cfg=cfg, deadline_seconds=rem, on_result=handle)
            if round_i >= cfg.link_augment_rounds or len(seen) >= cap:
                break
            round_i += 1
            new_urls = [u for u in harvested if u not in seen][: cap - len(seen)]
            if not new_urls:
                break
            seen.update(new_urls)
            frontier = new_urls
        record_discovered()
    finally:
        conn.close()
    return stored["n"]


def get_run(run_id: int, cfg: Config = config):
    conn = get_connection(cfg.db_path)
    try:
        return conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    finally:
        conn.close()


def discover_all(domains, max_pages, cfg: Config = config) -> dict:
    """Discover every domain's URLs up front, in parallel, recording each
    domain's page count the moment it's known — so all "detected pages" totals
    appear before any scanning starts (discovery is I/O-bound, so threads help).
    Returns {domain_id: [urls]}."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    seeds = {}
    if not domains:
        return seeds
    with ThreadPoolExecutor(max_workers=min(len(domains), 8)) as ex:
        futs = {ex.submit(discover_urls, d["domain"], max_pages, cfg): d for d in domains}
        for fut in as_completed(futs):
            d = futs[fut]
            try:
                urls = fut.result()
            except Exception:
                urls = []
            seeds[d["id"]] = urls
            conn = get_connection(cfg.db_path)
            try:
                conn.execute("UPDATE domains SET discovered=? WHERE id=?", (len(urls), d["id"]))
                conn.commit()
            finally:
                conn.close()
            print(f"  [{d['domain']}] detected {len(urls)} pages")
    return seeds


def execute_run(run_id: int, cfg: Config = config) -> int:
    """Run all pipeline stages (M1→M4) for an already-created run."""
    run = get_run(run_id, cfg=cfg)
    if run is None:
        raise ValueError(f"run {run_id} not found")
    lang = run["market_language"]
    cap = run["max_pages"]
    set_run_status(run_id, "running", cfg=cfg)
    try:
        domains = get_domains(run_id, cfg=cfg)
        # Phase 1: detect pages for ALL domains first (parallel) so every total
        # shows immediately; Phase 2: scan each using its precomputed seed.
        seeds = discover_all(domains, cap, cfg=cfg)
        for d in domains:
            n = crawl_domain(d["id"], d["domain"], lang, max_pages=cap, cfg=cfg,
                             seed=seeds.get(d["id"]))
            print(f"  [{d['domain']}] stored {n} pages")
        set_run_status(run_id, "crawled", cfg=cfg)

        # M2 — chunk + embed every page across all domains.
        n_chunks = embed_run(run_id, cfg=cfg)
        print(f"  embedded {n_chunks} chunks")
        set_run_status(run_id, "embedded", cfg=cfg)

        # M3 — discover topics + categories over all chunks (global).
        n_topics, n_cats = discover_topics(run_id, cfg=cfg)
        print(f"  discovered {n_topics} topics in {n_cats} categories")
        set_run_status(run_id, "topiced", cfg=cfg)

        # M4 — coverage strength, share, and state per topic.
        n_scored = score_coverage(run_id, cfg=cfg)
        print(f"  scored coverage for {n_scored} topics")
        set_run_status(run_id, "done", cfg=cfg)
    except Exception:
        set_run_status(run_id, "error", cfg=cfg)
        raise
    return run_id


def run_pipeline(
    own_domain: str,
    competitor_domains: List[str],
    market_language: Optional[str] = None,
    max_pages: Optional[int] = None,
    cfg: Config = config,
) -> int:
    """Create a run and execute the full pipeline (M1→M4) synchronously."""
    lang = market_language or cfg.default_market_language
    cap = max_pages if max_pages is not None else cfg.max_pages_per_domain
    run_id = create_run(own_domain, competitor_domains, lang, cap, cfg=cfg)
    return execute_run(run_id, cfg=cfg)


# --- CLI (make crawl DOMAIN=example.com) ------------------------------------

def _main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Crawl one domain (M1 debug).")
    parser.add_argument("--domain", required=True)
    parser.add_argument("--max-pages", type=int, default=None)
    parser.add_argument("--lang", default=None)
    args = parser.parse_args()

    lang = args.lang or config.default_market_language
    cap = args.max_pages if args.max_pages is not None else config.max_pages_per_domain

    run_id = create_run(args.domain, [], lang, cap)
    dom = get_domains(run_id)[0]
    print(f"Run {run_id}: crawling {args.domain} (cap {cap}, lang {lang})…")
    n = crawl_domain(dom["id"], args.domain, lang, max_pages=cap)
    set_run_status(run_id, "crawled")
    print(f"Done. Stored {n} pages with non-empty text for {args.domain}.")


if __name__ == "__main__":
    _main()
