"""Deterministic language-similarity scoring: your homepage vs a competitor's.

For each section (headlines, paragraphs) we produce two independent sub-scores:

  • semantic — cosine of the mean-pooled sentence embeddings ("same ideas,
    even in different words"), local sentence-transformers, deterministic.
  • lexical  — overlap of shared unigrams + bigrams after normalisation
    ("same actual words/phrases"), deterministic.

Both map to 0–100. A page profile (embeddings + token sets) is built once per
domain and scored against the own-domain profile — see build_profile / score.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

import numpy as np

from ..config import Config, config
from .chunk_embed import embed_texts
from .homepage import HomepageContent

# Compact English stopword list — enough to keep lexical overlap about content
# words, not glue words. (Deliberately small; not a linguistic resource.)
_STOPWORDS = {
    "the", "a", "an", "and", "or", "but", "if", "then", "so", "as", "of", "at",
    "by", "for", "with", "about", "into", "to", "from", "in", "on", "off", "up",
    "out", "over", "under", "is", "are", "was", "were", "be", "been", "being",
    "am", "do", "does", "did", "have", "has", "had", "can", "could", "will",
    "would", "shall", "should", "may", "might", "must", "this", "that", "these",
    "those", "it", "its", "you", "your", "yours", "we", "our", "ours", "they",
    "their", "them", "he", "she", "his", "her", "i", "me", "my", "not", "no",
    "yes", "all", "any", "every", "each", "more", "most", "some", "such", "than",
    "too", "very", "just", "also", "get", "got", "make", "made",
}

_WORD_RE = re.compile(r"[a-z0-9][a-z0-9'&+-]*")


@dataclass
class SectionProfile:
    """A section (headlines or paragraphs) reduced to what scoring needs."""
    n_items: int
    mean_vec: Optional[np.ndarray]   # mean-pooled, L2-normalised; None if empty
    unigrams: Set[str] = field(default_factory=set)
    bigrams: Set[Tuple[str, str]] = field(default_factory=set)


@dataclass
class PageProfile:
    domain: str
    headlines: SectionProfile
    paragraphs: SectionProfile


@dataclass
class SimilarityScores:
    """You-vs-competitor sub-scores (0–100) plus lexical evidence. None = a side
    had no headlines/paragraphs to compare."""
    headline_semantic: Optional[float]
    headline_lexical: Optional[float]
    paragraph_semantic: Optional[float]
    paragraph_lexical: Optional[float]
    shared_headline_phrases: List[str] = field(default_factory=list)
    shared_paragraph_phrases: List[str] = field(default_factory=list)


def _tokens(items: List[str]) -> List[str]:
    out: List[str] = []
    for it in items:
        out.extend(w for w in _WORD_RE.findall(it.lower())
                   if len(w) > 1 and w not in _STOPWORDS)
    return out


def _bigrams(tokens: List[str]) -> Set[Tuple[str, str]]:
    return set(zip(tokens, tokens[1:]))


def _profile_section(items: List[str], cfg: Config) -> SectionProfile:
    items = [i for i in items if i.strip()]
    if not items:
        return SectionProfile(n_items=0, mean_vec=None)
    vecs = embed_texts(items, cfg)          # already L2-normalised rows
    mean = vecs.mean(axis=0)
    norm = float(np.linalg.norm(mean))
    mean = mean / norm if norm else mean
    toks = _tokens(items)
    return SectionProfile(
        n_items=len(items), mean_vec=mean.astype(np.float32),
        unigrams=set(toks), bigrams=_bigrams(toks),
    )


def build_profile(content: HomepageContent, cfg: Config = config) -> PageProfile:
    """Embed + tokenise a homepage's sections once, ready to score repeatedly."""
    return PageProfile(
        domain=content.url,
        headlines=_profile_section(content.headlines, cfg),
        paragraphs=_profile_section(content.paragraphs, cfg),
    )


def _semantic(a: SectionProfile, b: SectionProfile) -> Optional[float]:
    if a.mean_vec is None or b.mean_vec is None:
        return None
    cos = float(np.dot(a.mean_vec, b.mean_vec))
    return round(max(0.0, min(1.0, cos)) * 100, 1)


def _overlap_coeff(a: set, b: set) -> float:
    """|A∩B| / min(|A|,|B|) — like Jaccard but not penalised when one page is
    much wordier than the other."""
    if not a or not b:
        return 0.0
    return len(a & b) / min(len(a), len(b))


def _lexical(a: SectionProfile, b: SectionProfile,
             cfg: Config) -> Tuple[Optional[float], List[str]]:
    if not a.unigrams or not b.unigrams:
        return None, []
    uni = _overlap_coeff(a.unigrams, b.unigrams)
    bi = _overlap_coeff(a.bigrams, b.bigrams)
    score = round((cfg.lexical_unigram_weight * uni
                   + cfg.lexical_bigram_weight * bi) * 100, 1)
    shared = sorted(" ".join(g) for g in (a.bigrams & b.bigrams))
    return score, shared[:12]


def score(own: PageProfile, comp: PageProfile,
          cfg: Config = config) -> SimilarityScores:
    """Score the competitor profile against the own-domain profile."""
    h_sem = _semantic(own.headlines, comp.headlines)
    p_sem = _semantic(own.paragraphs, comp.paragraphs)
    h_lex, h_shared = _lexical(own.headlines, comp.headlines, cfg)
    p_lex, p_shared = _lexical(own.paragraphs, comp.paragraphs, cfg)
    return SimilarityScores(
        headline_semantic=h_sem, headline_lexical=h_lex,
        paragraph_semantic=p_sem, paragraph_lexical=p_lex,
        shared_headline_phrases=h_shared, shared_paragraph_phrases=p_shared,
    )
