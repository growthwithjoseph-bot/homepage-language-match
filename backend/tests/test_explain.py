"""Explanation: deterministic fallback + graceful degradation when no LLM."""
from backend.config import Config
from backend.pipeline.explain import deterministic_explanation, explain
from backend.pipeline.homepage import HomepageContent
from backend.pipeline.scoring import SimilarityScores


def _scores():
    return SimilarityScores(
        headline_semantic=90, headline_lexical=5,
        paragraph_semantic=88, paragraph_lexical=8,
        shared_headline_phrases=["meeting notes"], shared_paragraph_phrases=[],
    )


def test_deterministic_explanation_reflects_scores_and_evidence():
    txt = deterministic_explanation("rival.com", _scores())
    assert "rival.com" in txt
    assert "meeting notes" in txt            # shared-phrase evidence included
    # high semantic + low lexical -> similar themes, different words
    assert "similar themes" in txt.lower()
    assert "different words" in txt.lower()


def test_explain_falls_back_when_llm_unreachable():
    # Point at a dead endpoint: the LLM call fails, deterministic text is returned.
    cfg = Config(explanation_enabled=True, llm_base_url="http://127.0.0.1:1/v1",
                 llm_api_key="", llm_timeout=1)
    own = HomepageContent(url="https://you.com", headlines=["Notes"], paragraphs=["x" * 60])
    txt = explain("you.com", "rival.com", own, own, _scores(), cfg)
    assert txt and "rival.com" in txt


def test_explain_disabled_uses_fallback():
    cfg = Config(explanation_enabled=False)
    own = HomepageContent(url="https://you.com", headlines=["Notes"], paragraphs=["x" * 60])
    txt = explain("you.com", "rival.com", own, own, _scores(), cfg)
    assert "meeting notes" in txt            # deterministic path, no network
