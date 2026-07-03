# CLAUDE.md — working conventions for this repo

You are building **Homepage Language Match**. The full spec is in `SPEC.md`. Read it first.

## What it does
Enter your domain + up to 5 competitors. For each competitor we fetch **only the
homepage**, extract its **headlines** and **paragraphs**, and score how similar
your messaging is to theirs on two axes — **meaning** (semantic) and **wording**
(lexical) — for each section. An optional LLM writes a short "why". The UI shows
per-competitor score cards, a meaning-vs-wording scatter, and a search history.

## How to work
- Keep modules small and readable; match the layout in SPEC §7.
- After a change, make it run and pass its check before moving on. Verify the app
  in the browser when a change is visible there.
- Commit logical units; never commit secrets (see below).

## Hard rules (do not drift)
- **Homepage only.** One page per domain — no crawling, sitemaps, or multi-page
  discovery. (That was the previous tool; it's gone.)
- **Scores are deterministic.** The four sub-scores are a pure function of the
  extracted text + embeddings (SPEC §4). No LLM in the number. Same input → same
  score. The LLM only writes the prose explanation.
- **Runs locally with no paid keys.** Default to local embeddings
  (`sentence-transformers`) and local/no LLM. Hosted embeddings and the LLM are
  optional upgrades behind config, always with a deterministic fallback.
- **All thresholds in `config.py`** (lexical weights, max competitors, LLM
  settings, embedding model) — never hardcoded in logic.
- **LLM is provider-agnostic and optional.** One OpenAI-compatible client
  (`explain.py`) via `TC_LLM_BASE_URL` / `TC_LLM_MODEL` / `TC_LLM_API_KEY`. Works
  with Ollama (local), Groq (free tier), etc. If it's unset or unreachable, the
  deterministic fallback runs — the tool never breaks on the LLM.
- **Secrets only in `.env`** (gitignored). Never hardcode a key or commit one.

## Commands (Makefile)
- `make dev` — run FastAPI with reload on :8000 (serves the API + frontend)
- `make test` — run tests
- `make install` / `make install-ml` — core deps / local embedding model deps

## Frontend
Static `frontend/` (index.html + app.js) served by FastAPI. Two tabs: **New
comparison** (form → report: cards + scatter) and **Recent comparisons**
(history). Each competitor has a stable colour shared by its scatter dot and card.
