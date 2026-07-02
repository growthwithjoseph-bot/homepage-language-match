"""M1 — polite fetching (SPEC §6.2).

Static fetch via httpx (async, HTTP/2) with:
  - robots.txt respected per host (config-toggleable)
  - per-host concurrency limit + small backoff
  - a Playwright fallback (optional) when extraction would be too thin.

The Playwright path is imported lazily so the repo runs without it installed.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlparse
from urllib.robotparser import RobotFileParser

import httpx

from ..config import Config, config

# Below this many characters we treat a static fetch as "too thin" and (if
# enabled) retry through Playwright for JS-rendered pages.
THIN_BODY_CHARS = 200


@dataclass
class FetchResult:
    url: str
    status: int
    html: Optional[str]
    etag: Optional[str]
    rendered: bool = False  # True if fetched via Playwright
    retry_after: Optional[float] = None  # server's Retry-After on a 429/503, if any


class RobotsCache:
    """Lazily fetch + cache one RobotFileParser per host."""

    def __init__(self, user_agent: str, respect: bool):
        self.user_agent = user_agent
        self.respect = respect
        self._cache: Dict[str, Optional[RobotFileParser]] = {}

    async def allowed(self, client: httpx.AsyncClient, url: str) -> bool:
        if not self.respect:
            return True
        p = urlparse(url)
        host_key = f"{p.scheme}://{p.netloc}"
        if host_key not in self._cache:
            self._cache[host_key] = await self._load(client, host_key)
        rp = self._cache[host_key]
        if rp is None:  # robots unreachable -> default allow (be lenient)
            return True
        return rp.can_fetch(self.user_agent, url)

    async def _load(
        self, client: httpx.AsyncClient, host_key: str
    ) -> Optional[RobotFileParser]:
        rp = RobotFileParser()
        try:
            resp = await client.get(f"{host_key}/robots.txt")
            if resp.status_code >= 400:
                return None
            rp.parse(resp.text.splitlines())
            return rp
        except Exception:
            return None


async def _maybe_render(url: str) -> Optional[str]:
    """Fetch fully-rendered HTML via Playwright, if it's installed."""
    try:
        from playwright.async_api import async_playwright
    except Exception:
        return None
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch()
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            html = await page.content()
            await browser.close()
            return html
    except Exception:
        return None


# Rate-limit / unavailable -> retry AND slow the whole host (shared cooldown).
RETRY_STATUSES = {429, 503}
# Transient failures that should retry that URL only (not throttle the host):
# status 0 is our marker for a network exception (timeout, reset, DNS blip);
# 5xx (except 503, handled above) are transient server errors.
NETWORK_ERROR_STATUS = 0
def _is_transient_error(status: int) -> bool:
    return status == NETWORK_ERROR_STATUS or (500 <= status < 600 and status != 503)


def _parse_retry_after(resp: httpx.Response) -> Optional[float]:
    """The server's Retry-After in seconds (seconds form only; HTTP-date is
    ignored in favour of our own backoff)."""
    ra = resp.headers.get("retry-after")
    if not ra:
        return None
    try:
        return max(0.0, float(ra))
    except ValueError:
        return None


async def fetch_url(
    client: httpx.AsyncClient,
    url: str,
    robots: RobotsCache,
    allow_render: bool = True,
) -> FetchResult:
    if not await robots.allowed(client, url):
        return FetchResult(url=url, status=999, html=None, etag=None)
    try:
        resp = await client.get(url)
    except Exception:
        return FetchResult(url=url, status=0, html=None, etag=None)

    etag = resp.headers.get("etag")
    if resp.status_code >= 400:
        return FetchResult(
            url=url, status=resp.status_code, html=None, etag=etag,
            retry_after=_parse_retry_after(resp),
        )

    html = resp.text
    if allow_render and (html is None or len(html) < THIN_BODY_CHARS):
        rendered = await _maybe_render(url)
        if rendered:
            return FetchResult(url, resp.status_code, rendered, etag, rendered=True)
    return FetchResult(url=url, status=resp.status_code, html=html, etag=etag)


async def fetch_many(
    urls: List[str],
    cfg: Config = config,
    allow_render: bool = True,
    deadline_seconds: Optional[float] = None,
    on_result=None,
) -> List[FetchResult]:
    """Fetch many URLs with a per-host concurrency cap and polite backoff.

    Stops starting new fetches once `deadline_seconds` of wall-clock have
    elapsed (the time budget), so a slow/huge site can't stall the run. If
    `on_result` is given it's called with each FetchResult as it completes —
    used to store pages incrementally for live per-domain progress.
    """
    robots = RobotsCache(cfg.user_agent, cfg.respect_robots)
    sem = asyncio.Semaphore(max(1, cfg.per_host_concurrency))
    headers = {"User-Agent": cfg.user_agent}
    limits = httpx.Limits(max_connections=cfg.per_host_concurrency)
    results: List[FetchResult] = []
    loop = asyncio.get_event_loop()
    start = loop.time()
    # Adaptive per-host pacing (AIMD) is the ONLY throttle: `pace` is the minimum
    # interval between request *starts* across all workers (a token bucket via
    # `next_slot`). Spacing starts alone prevents the burst-then-429 storm — no
    # separate host-wide cooldown, which would stack with the spacing and stall
    # the crawl. Start fast; multiply the interval up on every 429/503, ease it
    # back down on success: quick on tolerant sites, steadily complete on strict
    # ones. Capped at 1s (a punitive/blocking host is bounded by the time budget).
    PACE_MAX = 1.0
    pace = {"delay": cfg.per_request_delay_seconds}
    next_slot = 0.0  # earliest time the next request may start

    def expired() -> bool:
        return bool(deadline_seconds) and (loop.time() - start) > deadline_seconds

    async with httpx.AsyncClient(
        headers=headers,
        timeout=cfg.request_timeout,
        follow_redirects=True,
        http2=True,
        limits=limits,
    ) as client:

        async def worker(u: str) -> FetchResult:
            nonlocal next_slot
            async with sem:
                res = FetchResult(url=u, status=997, html=None, etag=None)
                for attempt in range(cfg.fetch_max_retries + 1):
                    if expired():  # budget spent -> skip remaining URLs
                        return FetchResult(url=u, status=997, html=None, etag=None)
                    # Reserve a spaced start slot so workers don't all fire at
                    # once and re-trip the limiter (this spacing IS the backoff).
                    now = loop.time()
                    start_at = max(now, next_slot)
                    next_slot = start_at + pace["delay"]
                    if start_at > now:
                        await asyncio.sleep(start_at - now)
                    res = await fetch_url(client, u, robots, allow_render)
                    if res.status in RETRY_STATUSES:
                        # rate-limited: widen the spacing so the steady rate drops,
                        # then retry (the gate re-spaces it) — don't drop the page.
                        pace["delay"] = min(PACE_MAX, max(0.1, pace["delay"] * 2))
                        if attempt < cfg.fetch_max_retries:
                            continue
                        break
                    if _is_transient_error(res.status):
                        # timeout / reset / 5xx -> retry just this URL, don't
                        # penalise the host. Recovers pages a connection blip drops.
                        if attempt < cfg.fetch_max_retries:
                            await asyncio.sleep(min(2.0 ** attempt, cfg.rate_limit_max_wait))
                            continue
                        break
                    if 200 <= res.status < 300:  # success -> ease the spacing back down
                        pace["delay"] = max(cfg.per_request_delay_seconds, pace["delay"] - 0.02)
                    break
                return res

        tasks = [asyncio.create_task(worker(u)) for u in urls]
        for fut in asyncio.as_completed(tasks):
            res = await fut
            results.append(res)
            if on_result is not None:
                on_result(res)
    return results


def fetch_all(
    urls: List[str],
    cfg: Config = config,
    allow_render: bool = True,
    deadline_seconds: Optional[float] = None,
    on_result=None,
):
    """Sync wrapper around fetch_many for CLI/synchronous run contexts."""
    return asyncio.run(
        fetch_many(
            urls,
            cfg=cfg,
            allow_render=allow_render,
            deadline_seconds=deadline_seconds,
            on_result=on_result,
        )
    )
