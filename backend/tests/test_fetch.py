"""Homepage fetcher: retry/backoff behaviour (rate-limit + transient errors)."""
import asyncio

import httpx

from backend.config import Config
from backend.pipeline import fetch as fetch_mod
from backend.pipeline.fetch import FetchResult, _parse_retry_after, fetch_many


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


def test_fetch_retries_transient_network_error(monkeypatch):
    """A connection blip (status 0) or 5xx must retry, not silently drop the page."""
    cfg = Config(fetch_max_retries=3, rate_limit_max_wait=0.01, per_host_concurrency=2,
                 per_request_delay_seconds=0)
    calls = {}

    async def fake(client, url, robots, allow_render=True):
        n = calls.get(url, 0)
        calls[url] = n + 1
        if url.endswith("/net"):
            return (FetchResult(url=url, status=0, html=None, etag=None) if n < 2
                    else FetchResult(url=url, status=200, html="<html>net ok</html>", etag=None))
        return (FetchResult(url=url, status=500, html=None, etag=None) if n < 1
                else FetchResult(url=url, status=200, html="<html>500 ok</html>", etag=None))

    monkeypatch.setattr(fetch_mod, "fetch_url", fake)
    res = asyncio.run(fetch_many(["https://x.com/net", "https://x.com/svc"], cfg=cfg))
    by = {r.url: r for r in res}
    assert by["https://x.com/net"].status == 200 and by["https://x.com/net"].html
    assert by["https://x.com/svc"].status == 200 and by["https://x.com/svc"].html
    assert calls["https://x.com/net"] == 3  # two failures then success


def test_fetch_recovers_all_under_throttling(monkeypatch):
    """Concurrent fetches, each 429'd once, must ALL be recovered (no drops)."""
    cfg = Config(fetch_max_retries=3, rate_limit_max_wait=0.01,
                 per_host_concurrency=8, per_request_delay_seconds=0)
    hits = {}

    async def fake(client, url, robots, allow_render=True):
        hits[url] = hits.get(url, 0) + 1
        if hits[url] == 1:
            return FetchResult(url=url, status=429, html=None, etag=None, retry_after=0.0)
        return FetchResult(url=url, status=200, html=f"<html>{url}</html>", etag=None)

    monkeypatch.setattr(fetch_mod, "fetch_url", fake)
    urls = [f"https://x.com/p{i}" for i in range(12)]
    res = asyncio.run(fetch_many(urls, cfg=cfg))
    assert len(res) == 12
    assert all(r.status == 200 and r.html for r in res)


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
