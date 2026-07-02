"""M1 — URL discovery (SPEC §6.1).

Prefer declared URLs over blind crawling:
  1. robots.txt -> Sitemap: directives
  2. expand sitemaps via trafilatura
  3. fallback to a focused crawl only when no sitemap yields URLs
Then filter to content pages and cap at max_pages_per_domain.
"""
from __future__ import annotations

import re
import threading
from typing import List, Optional
from urllib.parse import urldefrag, urljoin, urlparse

from ..config import Config, config

# href="…" extraction for link augmentation (catches pages a sitemap omits).
_HREF_PAT = re.compile(r"""href\s*=\s*["']([^"'#][^"']*)["']""", re.IGNORECASE)

# URL path fragments that almost never point at unique article content.
_NON_CONTENT_PAT = re.compile(
    r"""
    \.(?:jpg|jpeg|png|gif|svg|webp|ico|css|js|mjs|json|xml|rss|atom|pdf|zip|
        gz|mp4|mp3|woff2?|ttf|eot|map)(?:$|\?)   # asset extensions
    | /(?:tag|tags|category|categories|author|page|search|cart|checkout|
        login|signin|signup|account|wp-json|wp-admin|feed|amp)(?:/|$)
    """,
    re.IGNORECASE | re.VERBOSE,
)


def normalize_base(domain: str) -> str:
    """Turn 'example.com' or 'http://example.com/x' into 'https://example.com'."""
    domain = domain.strip()
    if not domain.startswith(("http://", "https://")):
        domain = "https://" + domain
    p = urlparse(domain)
    scheme = p.scheme or "https"
    return f"{scheme}://{p.netloc}"


def registrable_host(url: str) -> str:
    """Host without a leading 'www.' — used to keep discovery on-domain."""
    host = (urlparse(url).netloc or "").lower()
    return host[4:] if host.startswith("www.") else host


def build_exclude_regex(patterns) -> Optional["re.Pattern"]:
    """Compile path-stem patterns into one regex (matches a stem starting a
    path segment, e.g. '/careers', '/en/jobs/1', '/terms-of-service')."""
    if not patterns:
        return None
    alt = "|".join(re.escape(p) for p in patterns)
    return re.compile(r"(?:^|/)(?:%s)(?:[-/?#]|$)" % alt, re.IGNORECASE)


def is_content_url(url: str, base_host: str, exclude_re: Optional["re.Pattern"] = None) -> bool:
    """Keep on-domain http(s) URLs that look like real content pages.

    Drops assets/boilerplate, off-domain links, and anything matching the
    exclude patterns (careers/hiring, legal/terms — see config).
    """
    try:
        p = urlparse(url)
    except ValueError:
        return False
    if p.scheme not in ("http", "https"):
        return False
    if registrable_host(url) != base_host:
        return False
    if _NON_CONTENT_PAT.search(url):
        return False
    if exclude_re is not None and exclude_re.search(p.path or ""):
        return False
    return True


def extract_links(html: str, page_url: str, base_host: str,
                  exclude_re: Optional["re.Pattern"] = None) -> List[str]:
    """On-domain content URLs linked from a page's HTML (absolute, de-fragmented,
    deduped). Used to follow pages a sitemap misses. Skips non-http hrefs."""
    if not html:
        return []
    out, seen = [], set()
    for m in _HREF_PAT.finditer(html):
        raw = m.group(1).strip()
        if not raw or raw.lower().startswith(("mailto:", "tel:", "javascript:", "data:")):
            continue
        url = urldefrag(urljoin(page_url, raw))[0]
        if url in seen:
            continue
        seen.add(url)
        if is_content_url(url, base_host, exclude_re):
            out.append(url)
    return out


def _run_with_timeout(fn, timeout: float):
    """Run fn() in a daemon thread; return its result, or None if it exceeds
    `timeout` (the thread is abandoned — it dies with the process). Neither
    sitemap expansion nor focused crawling has an internal timeout, so this is
    how we stop a huge/slow site (e.g. notion.com's giant sitemap) stalling a run."""
    box = {"result": None}

    def work():
        try:
            box["result"] = fn()
        except Exception:
            box["result"] = None

    if not timeout:
        work()
        return box["result"]
    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    return box["result"]


def _from_sitemaps(base: str, timeout: float = 0.0) -> List[str]:
    def work():
        from trafilatura.sitemaps import sitemap_search

        return list(sitemap_search(base, target_lang=None) or [])

    urls = _run_with_timeout(work, timeout)
    return urls or []


_LOC_RE = re.compile(r"<loc>\s*([^<\s]+)\s*</loc>", re.IGNORECASE)


def _from_sitemap_direct(base: str, cfg: Config, timeout: float = 0.0) -> List[str]:
    """Fetch and parse the sitemap ourselves — a robust backstop for when
    trafilatura's sitemap_search comes up empty (it silently fails on some hosts,
    e.g. granola.ai, whose valid sitemap it can't read). We look at robots.txt
    Sitemap: directives plus the common paths, follow <sitemapindex> children,
    and collect every <loc>. Bounded by a wall-clock timeout and a sitemap cap."""
    import httpx

    def work():
        out, seen = [], set()
        headers = {"User-Agent": cfg.user_agent}
        with httpx.Client(headers=headers, follow_redirects=True, timeout=15.0) as client:
            def fetch(url):
                try:
                    r = client.get(url)
                    return r.text if r.status_code == 200 else None
                except Exception:
                    return None

            candidates = []
            robots = fetch(base + "/robots.txt")
            if robots:
                for line in robots.splitlines():
                    if line.lower().startswith("sitemap:"):
                        candidates.append(line.split(":", 1)[1].strip())
            candidates += [base + "/sitemap.xml", base + "/sitemap_index.xml"]

            queue = list(dict.fromkeys(candidates))
            while queue and len(seen) < 50:              # bound how many sitemaps
                sm = queue.pop(0)
                if sm in seen:
                    continue
                seen.add(sm)
                text = fetch(sm)
                if not text:
                    continue
                locs = _LOC_RE.findall(text)
                if "<sitemapindex" in text.lower():      # index -> queue children
                    queue.extend(l for l in locs if l not in seen)
                else:
                    out.extend(locs)
        return out

    urls = _run_with_timeout(work, timeout)
    return urls or []


def _from_focused_crawl(base: str, max_urls: int, timeout: float = 0.0) -> List[str]:
    """Sitemap-less fallback. Runs in a daemon thread with a wall-clock timeout —
    focused_crawler has no internal timeout and can hang on slow sites. On
    timeout we return whatever it produced (often nothing), and the caller
    proceeds with at least the homepage."""
    result = {"urls": []}

    def work():
        try:
            from trafilatura.spider import focused_crawler

            # focused_crawler handles robots, the frontier and dedup itself.
            to_visit, known = focused_crawler(
                base, max_seen_urls=max_urls, max_known_urls=max_urls * 4
            )
            seen = set(known or [])
            seen.update(to_visit or [])
            result["urls"] = list(seen)
        except Exception:
            pass

    if not timeout:
        work()
        return result["urls"]

    t = threading.Thread(target=work, daemon=True)
    t.start()
    t.join(timeout)
    return result["urls"]  # empty if it timed out (thread is a daemon, dies with us)


# Treat a non-positive cap as "all pages" (bounded by the crawl time budget).
_UNLIMITED = 1_000_000


def discover_urls(
    domain: str,
    max_pages: Optional[int] = None,
    cfg: Config = config,
) -> List[str]:
    """Return content URLs for a domain (sitemap first).

    max_pages None -> config default; max_pages <= 0 -> all pages (the crawl
    time budget is the real guardrail). The sitemap-less focused-crawl fallback
    is always bounded by cfg.focused_crawl_max_urls.
    """
    if max_pages is None:
        cap = cfg.max_pages_per_domain
    elif max_pages <= 0:
        cap = _UNLIMITED
    else:
        cap = max_pages
    base = normalize_base(domain)
    base_host = registrable_host(base)
    exclude_re = build_exclude_regex(cfg.exclude_url_patterns)

    candidates = _from_sitemaps(base, cfg.sitemap_timeout_seconds)
    if not candidates:
        # trafilatura found nothing — fetch/parse the sitemap ourselves (it
        # silently fails on some hosts whose sitemap is perfectly valid).
        candidates = _from_sitemap_direct(base, cfg, cfg.sitemap_timeout_seconds)
    if not candidates:
        # Still nothing -> no usable sitemap. Follow links, bounded by the smaller
        # of the requested cap and the focused-crawl ceiling.
        focused_max = min(cap, cfg.focused_crawl_max_urls)
        candidates = _from_focused_crawl(
            base, focused_max, cfg.focused_crawl_timeout_seconds
        )

    # Filter, dedupe (stable order), and cap.
    seen = set()
    out: List[str] = []
    for u in candidates:
        if u in seen or not is_content_url(u, base_host, exclude_re):
            continue
        seen.add(u)
        out.append(u)
        if len(out) >= cap:
            break
    # Always include the homepage as a fallback seed.
    if base not in seen:
        out.insert(0, base)
    return out[:cap]


if __name__ == "__main__":  # quick manual check: python -m backend.pipeline.discover example.com
    import sys

    dom = sys.argv[1] if len(sys.argv) > 1 else "example.com"
    found = discover_urls(dom, max_pages=20)
    print(f"{len(found)} URLs for {dom}:")
    for u in found[:20]:
        print(" ", u)
