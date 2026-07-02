"""Deterministic language-similarity scoring."""
from backend.pipeline.homepage import HomepageContent
from backend.pipeline.scoring import build_profile, score


def _page(url, headlines, paragraphs):
    return HomepageContent(url=url, headlines=headlines, paragraphs=paragraphs)


OWN = _page(
    "https://you.com",
    ["AI notetaker for every meeting", "Never take notes again"],
    ["Our AI notetaker captures every meeting and writes the summary for you."],
)
TWIN = _page(  # near-identical messaging + wording
    "https://twin.com",
    ["AI notetaker for every meeting", "Never take notes again"],
    ["The AI notetaker captures every meeting and writes your summary automatically."],
)
DIFFERENT = _page(
    "https://other.com",
    ["Industrial pumps for heavy machinery", "Reliable hydraulic systems"],
    ["We manufacture rugged hydraulic pumps for mining and construction equipment."],
)


def test_scores_are_deterministic():
    own = build_profile(OWN)
    a = score(own, build_profile(TWIN))
    b = score(own, build_profile(TWIN))
    assert (a.headline_semantic, a.headline_lexical,
            a.paragraph_semantic, a.paragraph_lexical) == \
           (b.headline_semantic, b.headline_lexical,
            b.paragraph_semantic, b.paragraph_lexical)


def test_identical_page_scores_max():
    own = build_profile(OWN)
    s = score(own, build_profile(OWN))
    assert s.headline_semantic == 100.0 and s.headline_lexical == 100.0
    assert s.paragraph_semantic == 100.0 and s.paragraph_lexical == 100.0


def test_twin_beats_unrelated_on_every_score():
    own = build_profile(OWN)
    twin = score(own, build_profile(TWIN))
    diff = score(own, build_profile(DIFFERENT))
    assert twin.headline_semantic > diff.headline_semantic
    assert twin.paragraph_semantic > diff.paragraph_semantic
    assert twin.headline_lexical > diff.headline_lexical
    # the twin shares real phrases; the unrelated page shares ~none
    assert twin.shared_paragraph_phrases and not diff.shared_paragraph_phrases


def test_empty_section_scores_none():
    own = build_profile(OWN)
    no_paras = score(own, build_profile(_page("https://x.com", ["Some headline here"], [])))
    assert no_paras.paragraph_semantic is None and no_paras.paragraph_lexical is None
    assert no_paras.headline_semantic is not None
