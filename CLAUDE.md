# CLAUDE.md — working conventions for this repo

You are building **Topic Coverage**. The full spec is in `SPEC.md`. Read it first.

## How to work
- **Build milestone by milestone** (SPEC §4: M0 → M6). Do not scaffold everything at once. After each milestone, make it run, pass its acceptance check, and commit before starting the next.
- After each milestone, briefly state what you built and how you verified it.
- Prefer small, readable modules matching the layout in SPEC §10.

## Hard rules (do not drift)
- **Coverage only.** No demand, no "white space", no authority scoring. If you're tempted to add any, stop — those are explicitly out of scope (SPEC §1, §12).
- **Topics are content-driven** (clustered from crawled content), never a hardcoded list.
- **All thresholds in `config.py`** (δ parity band, similarity threshold, page caps, cluster sizes) — never hardcoded in logic.
- **Must run locally with no paid API keys**: default to local embeddings (`sentence-transformers`) and term-based topic labels; treat hosted embeddings / LLM labels as optional upgrades behind config.
- **Be polite when crawling**: respect `robots.txt`, rate-limit per host, honour `max_pages_per_domain`.
- **Determinism where it matters**: the coverage state function (SPEC §6.6) is a pure rule, not a model.

## Commands (define these in the Makefile)
- `make dev` — run FastAPI with reload
- `make test` — run tests
- `make crawl DOMAIN=example.com` — crawl one domain (handy for M1 debugging)

## Verifying each milestone
Use the per-milestone acceptance checks in SPEC §4. Add a tiny test or a CLI command per stage so you can prove it works on one real domain before wiring the next stage.

## Frontend
Port the layout from `reference/radial-map.js` (a working radial generator). Build the UI against `reference/sample-map.json` first (no backend needed), then point it at the real `/runs/{id}/map` endpoint. Colour nodes by coverage state using the palette in SPEC §2/§9.
