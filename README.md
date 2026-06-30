# Topic Coverage

Crawl a brand's site and its competitors', discover the topics each writes about, and see — as a radial map — **who covers what, and who covers it more**. A pure content-coverage comparison (no demand, no authority).

See **`SPEC.md`** for the full build specification and **`CLAUDE.md`** for working conventions.

## Quickstart (target state once built)

```bash
# 1. install
make install            # or: pip install -e .  &&  playwright install chromium

# 2. run the API
make dev                # FastAPI on http://localhost:8000

# 3. start an analysis
curl -X POST localhost:8000/runs \
  -H 'content-type: application/json' \
  -d '{"own_domain":"asana.com","competitor_domains":["monday.com","clickup.com","notion.so"]}'

# 4. open the UI
open frontend/index.html   # shows the radial coverage map for the latest run
```

## How it works (one line)
crawl → extract clean content → chunk + embed → cluster into topics (across all domains) → score each domain's coverage per topic → render the radial map.

## Runs with no API keys
Defaults to local embeddings (`sentence-transformers`) and term-based topic labels, so it works offline. Add an embeddings/LLM provider via `.env` for higher-quality labels (optional).
