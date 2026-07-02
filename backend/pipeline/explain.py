"""The "why" behind a similarity score — an LLM explanation with a safe fallback.

Uses ONE OpenAI-compatible chat client (cfg.llm_base_url / llm_model /
llm_api_key), so the same code runs against local Ollama, Groq, xAI, OpenAI,
self-hosted vLLM — whatever the deploy points it at. The explanation is optional:
when the endpoint is unset, unreachable, or errors, a deterministic explanation
built from the scores + shared phrases is used instead, so the tool never breaks.
"""
from __future__ import annotations

from typing import List, Optional

from ..config import Config, config
from .homepage import HomepageContent
from .scoring import SimilarityScores


def _bullets(items: List[str], n: int) -> str:
    items = [i for i in items[:n]]
    return "\n".join(f"- {i}" for i in items) if items else "(none)"


def _prompt(own_name: str, comp_name: str, own: HomepageContent,
            comp: HomepageContent, s: SimilarityScores) -> str:
    shared = s.shared_headline_phrases + s.shared_paragraph_phrases
    return f"""You compare how two companies position themselves on their homepages.

OWN: {own_name}
COMPETITOR: {comp_name}

Language-similarity scores (0-100; higher = more similar):
- Headlines, meaning: {s.headline_semantic}
- Headlines, wording: {s.headline_lexical}
- Paragraphs, meaning: {s.paragraph_semantic}
- Paragraphs, wording: {s.paragraph_lexical}

{own_name} headlines:
{_bullets(own.headlines, 10)}

{comp_name} headlines:
{_bullets(comp.headlines, 10)}

Phrases both use: {", ".join(shared) if shared else "none"}

In 2-3 plain sentences, explain WHY these scores look this way: what themes or
claims the two homepages share, and where they diverge in positioning or tone.
Be concrete and specific to these companies. Do not restate the numbers."""


def _chat(prompt: str, cfg: Config) -> Optional[str]:
    """Call an OpenAI-compatible /chat/completions endpoint. None on any failure."""
    import httpx

    url = cfg.llm_base_url.rstrip("/") + "/chat/completions"
    headers = {"Content-Type": "application/json"}
    if cfg.llm_api_key:
        headers["Authorization"] = f"Bearer {cfg.llm_api_key}"
    try:
        r = httpx.post(url, headers=headers, timeout=cfg.llm_timeout, json={
            "model": cfg.llm_model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,
            "max_tokens": 240,
            "stream": False,
        })
        if r.status_code != 200:
            return None
        text = r.json()["choices"][0]["message"]["content"]
        return (text or "").strip() or None
    except Exception:
        return None


def _level(score: Optional[float], bands, default="") -> str:
    if score is None:
        return default
    for threshold, label in bands:
        if score >= threshold:
            return label
    return bands[-1][1]


def deterministic_explanation(comp_name: str, s: SimilarityScores) -> str:
    """Fallback explanation assembled from the scores + shared-phrase evidence —
    used when no LLM endpoint is available."""
    sem = [v for v in (s.headline_semantic, s.paragraph_semantic) if v is not None]
    lex = [v for v in (s.headline_lexical, s.paragraph_lexical) if v is not None]
    if not sem:
        return f"Not enough homepage text to compare against {comp_name}."
    avg_sem = sum(sem) / len(sem)
    avg_lex = (sum(lex) / len(lex)) if lex else 0.0

    meaning = _level(avg_sem, [(85, "talks about very similar themes to yours"),
                               (65, "shares a fair amount of thematic overlap with yours"),
                               (0, "takes a fairly different thematic angle from yours")])
    wording = _level(avg_lex, [(35, "and reuses much of the same phrasing"),
                               (15, "but with only some shared vocabulary"),
                               (0, "but in noticeably different words")])
    out = f"{comp_name}'s homepage {meaning} {wording}."
    shared = s.shared_headline_phrases + s.shared_paragraph_phrases
    if shared:
        out += " Shared phrases include: " + ", ".join(shared[:5]) + "."
    return out


def explain(own_name: str, comp_name: str, own: HomepageContent,
            comp: HomepageContent, s: SimilarityScores,
            cfg: Config = config) -> str:
    """LLM explanation if enabled + reachable; otherwise the deterministic one."""
    if cfg.explanation_enabled:
        text = _chat(_prompt(own_name, comp_name, own, comp, s), cfg)
        if text:
            return text
    return deterministic_explanation(comp_name, s)
