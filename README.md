---
title: Homepage Language Match
emoji: 🔤
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# Homepage Language Match

Compare how similar your **homepage messaging** is to your competitors'. Enter
your domain and up to 5 competitors; for each, the tool fetches **only the
homepage**, pulls out its **headlines** and **paragraphs**, and scores the
similarity of your messaging to theirs on two axes:

- **Meaning (semantic)** — do they say the *same things*, even in different words?
- **Wording (lexical)** — do they use the *same actual words/phrases*?

…for headlines and for paragraphs (four 0–100 scores per competitor), plus an
optional LLM-written explanation of *why*. It's a **messaging-analysis** tool —
no crawling, no SEO, no keyword or authority scoring.

See **`SPEC.md`** for the full spec, **`CLAUDE.md`** for conventions, and
**`DEPLOY.md`** to put it online.

## Quickstart

```bash
make install-ml          # deps incl. the local embedding model
make dev                 # FastAPI + UI on http://localhost:8000
```

Open http://localhost:8000, enter your domain and competitors, and hit
**Compare**. Or via the API:

```bash
curl -X POST localhost:8000/runs \
  -H 'content-type: application/json' \
  -d '{"own_domain":"fathom.ai","competitor_domains":["otter.ai","fireflies.ai"]}'
# then poll GET /runs/{id} until "done", and read GET /runs/{id}/report
```

## How it works
fetch each homepage → extract headlines + paragraphs (lxml) → embed locally and
compute **deterministic** semantic + lexical scores (you vs each competitor) →
optional LLM "why" → show per-competitor cards, a meaning-vs-wording scatter, and
a search history.

## Runs with no API keys
Scores use **local embeddings** (`sentence-transformers`) — no key needed, and
they're fully deterministic (same input → same score). The LLM explanation is
**optional and provider-agnostic** (one OpenAI-compatible client): point it at
local **Ollama** or a free **Groq** key via `TC_LLM_BASE_URL` / `TC_LLM_MODEL` /
`TC_LLM_API_KEY`; if it's unset or unreachable, a deterministic explanation is
used instead. Keys live only in a gitignored `.env` — never in the repo.
