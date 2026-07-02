"""Homepage structured extraction.

The tool compares one page per domain — the homepage — so we pull out its two
kinds of copy separately: headlines (h1–h3) and paragraphs (body <p> blocks).
These feed the language-similarity scores (semantic + lexical) in scoring.py.

Parsing is done with lxml directly (not trafilatura) because we need the page's
*structure* — which text is a heading vs. a paragraph — not one flat blob.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List

# Headings up to h3; h4+ is almost always footer/legal/navigation noise.
_HEADING_TAGS = ("h1", "h2", "h3")
# Containers whose text is boilerplate, not homepage messaging.
_STRIP_TAGS = ("script", "style", "noscript", "template", "svg", "nav", "footer")

# A paragraph shorter than this is usually a label/caption/cookie line, not copy.
MIN_PARAGRAPH_CHARS = 40
# A headline this short is usually an icon label or stray character.
MIN_HEADLINE_CHARS = 3


@dataclass
class HomepageContent:
    url: str
    title: str = ""
    headlines: List[str] = field(default_factory=list)
    paragraphs: List[str] = field(default_factory=list)

    def is_empty(self) -> bool:
        return not self.headlines and not self.paragraphs


def _norm(text: str) -> str:
    """Collapse whitespace to single spaces and trim."""
    return re.sub(r"\s+", " ", text or "").strip()


def _dedupe(items: List[str]) -> List[str]:
    """Drop exact/case-insensitive duplicates, keep first-seen order."""
    seen, out = set(), []
    for it in items:
        key = it.lower()
        if key not in seen:
            seen.add(key)
            out.append(it)
    return out


def extract_homepage(html: str, url: str) -> HomepageContent:
    """Parse headlines (h1–h3) and paragraphs (<p>) from a homepage's HTML."""
    content = HomepageContent(url=url)
    if not html:
        return content

    import lxml.html

    try:
        tree = lxml.html.fromstring(html)
    except Exception:
        return content

    # Drop boilerplate containers so their text can't leak into headings/paras.
    for tag in _STRIP_TAGS:
        for el in tree.iter(tag):
            el.drop_tree()

    t = tree.findtext(".//title")
    content.title = _norm(t) if t else ""

    headlines = []
    for tag in _HEADING_TAGS:
        for el in tree.iter(tag):
            txt = _norm(el.text_content())
            if len(txt) >= MIN_HEADLINE_CHARS:
                headlines.append(txt)
    content.headlines = _dedupe(headlines)

    paragraphs = []
    for el in tree.iter("p"):
        txt = _norm(el.text_content())
        if len(txt) >= MIN_PARAGRAPH_CHARS:
            paragraphs.append(txt)
    content.paragraphs = _dedupe(paragraphs)

    return content


# --- CLI: python -m backend.pipeline.homepage https://example.com ----------

def _main() -> None:
    import sys

    from ..config import config
    from .fetch import fetch_all

    url = sys.argv[1] if len(sys.argv) > 1 else "https://example.com"
    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    grabbed = {}
    fetch_all([url], cfg=config, on_result=lambda r: grabbed.update({"res": r}))
    res = grabbed.get("res")
    if res is None or not res.html:
        print(f"Could not fetch {url} (status {getattr(res, 'status', '?')})")
        return

    hp = extract_homepage(res.html, url)
    print(f"# {hp.title}\n{url}\n")
    print(f"Headlines ({len(hp.headlines)}):")
    for h in hp.headlines[:20]:
        print(f"  • {h}")
    print(f"\nParagraphs ({len(hp.paragraphs)}):")
    for p in hp.paragraphs[:10]:
        print(f"  • {p[:120]}{'…' if len(p) > 120 else ''}")


if __name__ == "__main__":
    _main()
