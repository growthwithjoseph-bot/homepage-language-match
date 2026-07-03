# Homepage Language Match — Build Specification

**Author:** Giuseppe Milo · **Audience:** the developer / Claude Code building this.

## 1. What it is
A tool that compares how similar your homepage's **messaging** is to your
competitors'. You enter your domain and up to 5 competitor domains; for each we
fetch **only the homepage**, extract its **headlines** and **paragraphs**, and
produce four 0–100 similarity sub-scores of you-vs-that-competitor:

|                | Meaning (semantic) | Wording (lexical) |
|----------------|--------------------|-------------------|
| **Headlines**  | embedding cosine   | phrase/word overlap |
| **Paragraphs** | embedding cosine   | phrase/word overlap |

Plus an optional LLM-written explanation of *why* the scores look that way.

**Out of scope:** crawling, sitemaps, multi-page analysis, SEO/keyword/authority
scoring. One page per domain — the homepage.

## 2. Flow
1. `POST /runs {own_domain, competitor_domains[]}` → creates a run (competitors
   capped at `max_competitors`), executes in a background thread.
2. Fetch every homepage (one request each, concurrent), extract headlines +
   paragraphs, store them.
3. Build a per-page profile (mean-pooled section embeddings + token sets); score
   each competitor against the own domain; write an explanation.
4. UI polls `GET /runs/{id}` until `done`, then reads `GET /runs/{id}/report`.

## 3. Extraction (`pipeline/homepage.py`)
Parse the homepage HTML with lxml. **Headlines** = de-duped text of `h1`–`h3`
(≥ 3 chars). **Paragraphs** = de-duped `<p>` text (≥ 40 chars). Strip
`script/style/nav/footer` first so boilerplate can't leak in.

## 4. Scoring (`pipeline/scoring.py`) — deterministic
Per section (headlines, paragraphs), you-vs-competitor:
- **Semantic**: cosine of the mean-pooled, L2-normalised sentence embeddings
  (local `sentence-transformers`), mapped to 0–100.
- **Lexical**: `unigram_weight · overlap(unigrams) + bigram_weight ·
  overlap(bigrams)`, using the overlap coefficient `|A∩B| / min(|A|,|B|)` on
  stop-word-filtered tokens, mapped to 0–100. Shared bigrams are kept as evidence.

Empty sections score `None`. Same inputs always give the same numbers — no model
in the score.

## 5. Explanation (`pipeline/explain.py`) — optional, with fallback
One OpenAI-compatible `/chat/completions` client (works with Ollama, Groq, xAI,
OpenAI, self-hosted vLLM) selected by `TC_LLM_BASE_URL` / `TC_LLM_MODEL` /
`TC_LLM_API_KEY`. It gets both pages' text + the scores + shared phrases and
writes 2–3 sentences. If disabled/unreachable, a **deterministic explanation**
(assembled from the scores + shared phrases) is used, and the report flags which
was used (`explanation_ai`).

## 6. API
- `POST /runs` — start a comparison.
- `GET /runs` — history (recent comparisons, homepage-runs only).
- `GET /runs/{id}` — status (`running` / `done` / `error`).
- `GET /runs/{id}/report` — own summary + per-competitor `{scores, shared_*,
  explanation, explanation_ai, headlines, paragraphs}`.

## 7. Layout
```
backend/
  app.py            FastAPI app + routes + static frontend
  config.py         all thresholds / settings (env-overridable)
  db.py             SQLite: runs, domains, homepages, similarity
  pipeline/
    run.py          orchestration (fetch → extract → score → explain → store)
    fetch.py        polite async homepage fetching (retry/backoff)
    homepage.py     headline/paragraph extraction + normalize_base
    embed.py        text embeddings (local / OpenAI)
    scoring.py      deterministic semantic + lexical scores
    explain.py      LLM "why" + deterministic fallback
frontend/           index.html + app.js (tabs: compare / history)
```

## 8. Config (env-overridable, see `.env.example`)
`TC_MAX_COMPETITORS` (5), `TC_LEXICAL_UNIGRAM_WEIGHT` / `TC_LEXICAL_BIGRAM_WEIGHT`
(0.5/0.5), `TC_LOCAL_EMBEDDING_MODEL`, `TC_EXPLANATION`, `TC_LLM_BASE_URL` /
`TC_LLM_MODEL` / `TC_LLM_API_KEY`. Must run with **no keys** (local embeddings +
deterministic explanation).

## 9. Non-negotiables
Deterministic scores · homepage-only · local-first, no required paid keys · LLM
optional with fallback · thresholds in config · secrets only in gitignored `.env`.
