"""M1 unit checks that don't need the network: URL filtering, extraction,
and page storage. A live end-to-end crawl is exercised via `make crawl`."""
import asyncio
from pathlib import Path

import httpx

from backend.config import Config
from backend.db import get_connection, init_db
from backend.pipeline import fetch as fetch_mod
from backend.pipeline.discover import is_content_url, normalize_base, registrable_host
from backend.pipeline.extract import extract_page
from backend.pipeline.fetch import FetchResult, _parse_retry_after, fetch_many
from backend.pipeline.run import create_run, get_domains, _store_pages


def test_normalize_and_host():
    assert normalize_base("example.com") == "https://example.com"
    assert normalize_base("http://www.example.com/x") == "http://www.example.com"
    assert registrable_host("https://www.example.com/a") == "example.com"


def test_is_content_url_filters_assets_and_offdomain():
    h = "example.com"
    assert is_content_url("https://example.com/blog/post", h)
    assert not is_content_url("https://example.com/logo.png", h)
    assert not is_content_url("https://example.com/tag/news", h)
    assert not is_content_url("https://other.com/blog/post", h)


def test_is_content_url_excludes_careers_and_legal():
    from backend.config import config
    from backend.pipeline.discover import build_exclude_regex

    h = "example.com"
    ex = build_exclude_regex(config.exclude_url_patterns)
    # careers / hiring
    assert not is_content_url("https://example.com/careers", h, ex)
    assert not is_content_url("https://example.com/en-au/jobs/paris", h, ex)
    assert not is_content_url("https://example.com/about/hiring", h, ex)
    assert not is_content_url("https://example.com/life-at-example", h, ex)
    # legal / terms
    assert not is_content_url("https://example.com/terms-of-service", h, ex)
    assert not is_content_url("https://example.com/legal/privacy-policy", h, ex)
    assert not is_content_url("https://example.com/cookies", h, ex)
    # real content still passes
    assert is_content_url("https://example.com/blog/project-planning", h, ex)
    assert is_content_url("https://example.com/product/timeline", h, ex)


def test_extract_page_from_html():
    body = " ".join(
        ["Gantt charts help teams plan project timelines and milestones."] * 12
    )
    html = f"<html><head><title>Planning Guide</title></head><body><article><h1>Planning</h1><p>{body}</p></article></body></html>"
    page = extract_page(html, "https://example.com/planning", market_language="en")
    assert page is not None
    assert page.text and "Gantt" in page.text
    assert page.lang == "en"


def test_crawl_deadline_scales_with_urls():
    cfg = Config(crawl_seconds_per_url=2.0, crawl_time_budget_max_seconds=1800.0)
    assert cfg.crawl_deadline_for(10) == 20.0          # small site -> short
    assert cfg.crawl_deadline_for(715) == 1430.0       # large site -> not truncated
    assert cfg.crawl_deadline_for(5000) == 1800.0      # capped by the ceiling
    # seconds_per_url = 0 means no time limit at all
    assert Config(crawl_seconds_per_url=0).crawl_deadline_for(1000) is None


def test_parse_retry_after():
    def resp(val):
        return httpx.Response(429, headers={} if val is None else {"retry-after": val})
    assert _parse_retry_after(resp("5")) == 5.0
    assert _parse_retry_after(resp(None)) is None
    assert _parse_retry_after(resp("Wed, 21 Oct 2099 07:28:00 GMT")) is None  # HTTP-date -> backoff


def test_fetch_retries_then_succeeds_on_429(monkeypatch):
    """A host that returns 429 then recovers should yield the page, not drop it."""
    cfg = Config(fetch_max_retries=3, rate_limit_max_wait=0.01, per_host_concurrency=2)
    calls = {}

    async def fake_fetch_url(client, url, robots, allow_render=True):
        n = calls.get(url, 0)
        calls[url] = n + 1
        if n < 2:  # throttled on the first two attempts, then recovers
            return FetchResult(url=url, status=429, html=None, etag=None, retry_after=0.0)
        return FetchResult(url=url, status=200, html="<html>ok</html>", etag=None)

    monkeypatch.setattr(fetch_mod, "fetch_url", fake_fetch_url)
    results = asyncio.run(fetch_many(["https://x.com/a"], cfg=cfg))
    assert calls["https://x.com/a"] == 3          # retried past the two 429s
    assert results[0].status == 200 and results[0].html


def test_fetch_gives_up_after_max_retries(monkeypatch):
    """Persistent 429 is dropped after the retry budget (no infinite loop)."""
    cfg = Config(fetch_max_retries=2, rate_limit_max_wait=0.01, per_host_concurrency=1)
    calls = {"n": 0}

    async def always_429(client, url, robots, allow_render=True):
        calls["n"] += 1
        return FetchResult(url=url, status=429, html=None, etag=None, retry_after=0.0)

    monkeypatch.setattr(fetch_mod, "fetch_url", always_429)
    results = asyncio.run(fetch_many(["https://x.com/a"], cfg=cfg))
    assert calls["n"] == 3                         # initial try + 2 retries
    assert results[0].status == 429 and results[0].html is None


def test_store_pages_roundtrip(tmp_path: Path):
    cfg = Config(db_path=tmp_path / "m1.db")
    init_db(cfg.db_path)
    run_id = create_run("example.com", ["rival.com"], "en", 50, cfg=cfg)
    dom = get_domains(run_id, cfg=cfg)[0]
    n = _store_pages(
        dom["id"],
        [{"url": "https://example.com/p", "title": "P", "text": "hello world", "lang": "en", "etag": None}],
        cfg,
    )
    assert n == 1
    conn = get_connection(cfg.db_path)
    try:
        row = conn.execute("SELECT url, text FROM pages").fetchone()
    finally:
        conn.close()
    assert row["url"] == "https://example.com/p"
    assert row["text"] == "hello world"
