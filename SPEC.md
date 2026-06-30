# Topic Coverage — Build Specification

**Status:** Ready for implementation · **Author:** Giuseppe Milo · **Date:** 2026-06-30
**Audience:** the developer / Claude Code building this as a standalone project.

> Read this top to bottom once, then build **milestone by milestone** (§4). Each milestone is independently runnable and has its own acceptance check. Do not try to build everything at once.

---

## 1. What this is

**Topic Coverage** is a standalone tool that crawls a brand's website and its competitors', discovers the topics each one writes about, and shows — as a radial topic map — **who covers what, and who covers it more**. It answers one question:

> *"Across the topics in my category, where do I have more / less / no content than my competitors?"*

It is a **content comparison**, nothing more.

### What it is NOT (important — keep the scope honest)
- **Not demand.** It does not know what audiences search for or ask. There is no "white space" here (white space requires demand). Topics come *only* from content that actually exists.
- **Not authority.** Coverage = "does this site have content on the topic, and how much." It is **not** topical authority (which would also need rankings, backlinks, depth, off-site signals). Authority is a future, separate evolution — out of scope (§12).
- **Not a writer.** It diagnoses; it does not generate or publish content.

This tool is the diagnosis layer. (It originated as the "Topic Coverage" step of a larger product called Trendible; here it stands alone.)

---

## 2. Core concepts & definitions

**Domain** — a website being analysed. There is exactly one **own domain** and one or more **competitor domains**.

**Page** — a crawled content URL on a domain.

**Chunk** — a coherent passage of a page (~200–500 tokens). The unit we embed. A long page can touch several topics, so we work at chunk level.

**Topic** — a cluster of semantically similar chunks **across all domains** (content-driven, auto-discovered — §6.4). Each topic has a human-readable label and a centroid embedding. Topics are the leaves of the map.

**Category** — a super-cluster grouping related topics (e.g. "Integrations & API" groups *Public API*, *Webhooks*, *Zapier*). The inner ring of the map. ~8–14 categories total.

**Coverage strength** `S(domain, topic)` — how strongly a domain covers a topic. A function of how many of that domain's chunks fall in the topic and how strongly they match (§6.5). `0` means the domain does not cover the topic at all.

**Coverage share** — for a topic, the own domain's share of total coverage strength vs the sum of competitors':
`you% = S(own,t) / (S(own,t) + Σ S(comp_i,t))`.

**Coverage state** — the single label per topic that colours its node. Demand-free, derived only from coverage strengths (§6.6):

| State | Condition | Colour |
|---|---|---|
| `only_you` | you cover it, no competitor does | dark green `#15803d` |
| `you_lead` | both cover, your strength > strongest competitor + δ | green `#22c55e` |
| `even` | both cover, within the parity band δ | grey `#94a3b8` |
| `comp_lead` | both cover, a competitor's strength > yours + δ | orange `#fb923c` |
| `only_comp` | a competitor covers it, you don't | red `#ef4444` |

> Note there is **no "neither covers" state** — a topic only exists because some domain produced content for it. This is the structural reason white space cannot appear here.

`δ` (parity band) is a config threshold.

---

## 3. Inputs & outputs

**Input** (one analysis run):
```json
{
  "own_domain": "asana.com",
  "competitor_domains": ["monday.com", "clickup.com", "notion.so"],
  "market_language": "en",
  "max_pages_per_domain": 300
}
```

**Output:** a stored, queryable **coverage map**:
- categories → topics (the tree)
- per topic: coverage state, coverage share (you vs competitors), and the **detected content** behind it (matched sentences + source page URLs per domain)
- rendered as an interactive radial map in the browser.

---

## 4. Milestones (build in this order)

Each milestone must run and pass its acceptance check before moving on. Commit per milestone.

| # | Milestone | Deliverable | Acceptance check |
|---|---|---|---|
| **M0** | Project skeleton | Repo layout (§10), FastAPI app boots, SQLite schema created, `.env` config, `make dev` runs | `GET /health` returns 200; DB file created with all tables |
| **M1** | Crawl + extract | Given a domain, discover URLs (sitemap→crawl fallback) and extract clean main content per page | Run on one real domain → N pages stored in `pages` with non-empty `text`; respects `max_pages` + robots |
| **M2** | Chunk + embed | Split pages into chunks, embed them, store vectors | `chunks` table populated with embeddings; cosine query returns sensible neighbours |
| **M3** | Topic discovery | Cluster all chunks (all domains) into topics; label topics; group topics into categories | `topics` + `categories` populated; labels are readable; each chunk has a `topic_id` |
| **M4** | Coverage scoring | Compute `S(domain,topic)`, coverage share, and the coverage state per topic | `topic_coverage` populated; every topic has a state ∈ the 5 values; spot-checks look right |
| **M5** | API | Endpoints to trigger a run and read the map + per-topic detected content | `POST /runs` then `GET /runs/{id}/map` returns the full tree with states + shares + evidence |
| **M6** | Radial UI | Browser view: the radial coverage map + click→detail panel with detected content & links | Opening the app shows the map for a completed run; clicking a topic shows sentences + page links |

A run can be **synchronous and slow** for v1 (crawling takes minutes). Background/queue is a later concern (§12).

---

## 5. Architecture (pipeline)

```
INPUT (own + competitor domains)
        │
        ▼
[1] URL discovery  ── sitemap / robots / focused-crawl fallback        (per domain)
        │
        ▼
[2] Fetch + extract ── trafilatura (Playwright fallback for JS sites)  (per domain)
        │
        ▼
[3] Chunk + embed  ── ~200–500 tok chunks → embedding vectors          (per domain)
        │
        ▼
[4] Topic discovery ── cluster ALL chunks (every domain) → topics      (global, once)
        │              → label topics → group topics into categories
        ▼
[5] Coverage scoring ── per (domain,topic) strength → share → state    (global)
        │
        ▼
STORE (SQLite) ──► [6] API ──► [7] Radial UI
```

Stages 1–3 run per domain (parallelisable). Stage 4 is **global** — it must see every domain's chunks together so topics are shared vocabulary across domains (otherwise you can't compare). Stages 5–7 read the shared topics.

---

## 6. Pipeline detail

### 6.1 URL discovery
Prefer declared URLs over blind crawling:
1. Read `robots.txt` → `Sitemap:` directives.
2. Expand sitemaps (`trafilatura.sitemaps.sitemap_search()`); supplement with feeds.
3. Fallback only if no sitemap: `trafilatura.spider.focused_crawler()` (handles robots, frontier, dedup).
Filter to content pages (drop assets, tag/pagination/boilerplate URLs). Cap at `max_pages_per_domain`.

### 6.2 Fetch
- Static: `httpx` (async, HTTP/2), per-host concurrency limit + backoff, respect robots.
- JS-rendered fallback: if extraction is too thin (body < ~200 chars / SPA shell), re-fetch via **Playwright**. Keep it a fallback — it's slow.
- Cache by URL + `ETag`/`Last-Modified`; skip unchanged on re-runs.

### 6.3 Extract
Use **trafilatura** as primary extractor:
```python
import trafilatura
html = trafilatura.fetch_url(url)            # or Playwright-rendered HTML
doc = trafilatura.extract(
    html, output_format="markdown",
    include_comments=False, include_tables=True,
    with_metadata=True, favor_precision=True,
)
```
Keep page `title` and `url` (needed as evidence). Language-detect (`lingua`) and drop pages not in `market_language`.

### 6.4 Chunk → embed → discover topics
- **Chunk** extracted markdown by heading/section into ~200–500 token passages with slight overlap.
- **Embed** each chunk. Config-switch between a hosted API (OpenAI `text-embedding-3-small`) and a local model (`sentence-transformers`, e.g. `BAAI/bge-small-en-v1.5`). Default to local so the repo runs with no API key.
- **Discover topics over ALL chunks from ALL domains together** using **BERTopic** (sentence-transformers → UMAP → HDBSCAN → c-TF-IDF):
  - Each resulting cluster = a **topic**. Compute its centroid (mean of member chunk vectors). Keep representative chunks per topic (for evidence).
  - **Label** each topic with a short human name via the LLM over its representative chunks (BERTopic supports LLM labelling). Fallback: top c-TF-IDF terms.
  - Drop the HDBSCAN noise cluster (`-1`) or re-assign its chunks to nearest topic above a similarity floor.
  - Watch `min_cluster_size` / UMAP `n_neighbors` — these control how granular topics are. Make them config.
- **Group topics into categories:** run a coarse hierarchical clustering on the **topic centroids** (or BERTopic's hierarchical topics) to get ~8–14 super-clusters. Label each category with the LLM over its topic labels.

> Why content-driven: the tool is standalone with no demand/seed list. The topic universe is *defined by what the domains actually publish* — exactly the right basis for a coverage comparison.

### 6.5 Coverage strength
For each `(domain, topic)`:
- Collect the domain's chunks assigned to that topic (membership via BERTopic, or cosine of chunk vs topic centroid ≥ `sim_threshold`).
- `S(domain, topic)` = weighted count: `Σ over matched chunks of similarity`, then **normalise per topic** to `0..1` across domains (so the strongest domain on a topic ≈ 1). Also keep the raw page count.
- `S = 0` (and not "covered") if the domain has zero chunks clearing `sim_threshold` for that topic.

### 6.6 Coverage state + share (deterministic)
```python
def coverage_state(s_you, comp_strengths, delta):
    s_comp = max(comp_strengths) if comp_strengths else 0.0
    you_covers = s_you > 0
    comp_covers = s_comp > 0
    if you_covers and not comp_covers:      return "only_you"
    if comp_covers and not you_covers:      return "only_comp"
    # both cover:
    if s_you  > s_comp + delta:             return "you_lead"
    if s_comp > s_you  + delta:             return "comp_lead"
    return "even"
```
Coverage share: `you% = round(100 * S_you / (S_you + Σ S_comp))`, `competitors% = 100 - you%`. (When `only_comp`, you% = 0; when `only_you`, you% = 100.)

All thresholds (`delta`, `sim_threshold`, `min_cluster_size`, page caps) live in **config**, not code.

---

## 7. Data model (SQLite)

Store embeddings either via the **`sqlite-vec`** extension or as float32 blobs with cosine done in numpy (fine at this scale). Tables:

```sql
runs(            id, own_domain, competitor_domains_json, market_language,
                 max_pages, status, created_at, finished_at )
domains(         id, run_id, domain, is_own )
pages(           id, domain_id, url, title, text, lang, etag, fetched_at )
chunks(          id, page_id, domain_id, run_id, text, embedding, topic_id )
topics(          id, run_id, category_id, label, centroid, rep_chunk_ids_json )
categories(      id, run_id, label )
topic_coverage(  id, run_id, topic_id, domain_id, strength, page_count,
                 covered BOOL )          -- one row per (topic,domain)
topic_state(     id, run_id, topic_id, state, you_pct, competitors_pct )
```
`evidence` for the detail panel is derived: a topic's detected content for a domain = that domain's chunks where `chunks.topic_id = topic` → join `pages` for `url`, `title`, and the chunk `text` (the matched sentence/passage).

---

## 8. API (FastAPI)

```
GET  /health                         → {status:"ok"}

POST /runs                           → start an analysis
     body: {own_domain, competitor_domains[], market_language?, max_pages_per_domain?}
     → {run_id, status:"running"}

GET  /runs/{id}                      → {status, counts, progress}

GET  /runs/{id}/map                  → the full coverage map:
     {
       own_domain, competitors[],
       categories: [
         { id, label,
           topics: [ { id, label, state, you_pct, competitors_pct } ] }
       ]
     }

GET  /runs/{id}/topics/{topic_id}    → detail for one topic:
     {
       label, category, state, you_pct, competitors_pct,
       detected: {
         own:        [ {sentence, url, title} ],
         competitors:[ {domain, sentence, url, title} ]
       }
     }
```
v1 may run `POST /runs` synchronously (blocking) — acceptable while crawling. Return progress via `GET /runs/{id}` if you make it async.

---

## 9. Frontend — the radial coverage map

Plain HTML + JS + SVG (no framework, no build). Two pieces:

**(a) The radial map.** Root (own domain) in the centre → category nodes (inner ring) → topic leaves (outer ring) with curved edges and radial labels. Each topic dot is coloured by its `state` using the palette in §2. Legend on top. A **reference implementation of this exact layout already exists** and should be ported — see `reference/radial-map.js` (the `renderTopicalMap` generator: it lays out leaves on angular slots, places category nodes at the mean angle of their leaves, rotates labels, and draws quadratic edges). Feed it the `/map` response instead of the hardcoded sample data.

Palette: `only_you #15803d · you_lead #22c55e · even #94a3b8 · comp_lead #fb923c · only_comp #ef4444 · category #64748b`.

**(b) The detail panel (below the map).** On clicking a topic, call `/runs/{id}/topics/{topic_id}` and render:
- the coverage-state chip + topic label + category,
- the **share-of-coverage bar** (You % vs Competitors %),
- **"Content detected on this topic"** in two columns — *On your domain* and *On competitors* — each item showing the **matched sentence** (topic terms highlighted) and a **link to the source page** ("See more →"). Empty states: "No content detected on your domain for this topic." / competitor equivalent.

No navigation away from the page — this is a self-contained diagnosis.

---

## 10. Repo structure

```
topic-coverage/
  README.md
  SPEC.md                ← this file
  CLAUDE.md              ← working conventions for Claude Code
  .env.example
  Makefile               ← dev, run, test, crawl
  pyproject.toml
  backend/
    app.py               ← FastAPI app + routes
    config.py            ← thresholds, caps, model choices (env-overridable)
    db.py                ← SQLite schema + helpers
    pipeline/
      discover.py        ← M1 URL discovery
      fetch.py           ← M1 fetch (+ Playwright fallback)
      extract.py         ← M1 trafilatura extraction
      chunk_embed.py     ← M2 chunk + embed
      topics.py          ← M3 BERTopic clustering + labels + categories
      coverage.py        ← M4 strength, share, state
      run.py             ← orchestrates M1→M4 for a run
    tests/
  frontend/
    index.html
    app.js               ← fetch /map + /topics, render
    radial-map.js        ← ported from reference/
  reference/
    radial-map.js        ← proven layout generator (from the prototype)
    sample-map.json      ← a sample /map payload for UI dev without a backend
```

---

## 11. Tech stack

| Concern | Choice |
|---|---|
| Backend | **Python 3.11+, FastAPI, uvicorn** |
| Storage | **SQLite** (+ `sqlite-vec` or numpy-blob vectors) |
| URL discovery / crawl | `trafilatura` (sitemaps, feeds, focused_crawler) |
| HTTP | `httpx` (async) |
| JS rendering (fallback) | `Playwright` |
| Extraction | `trafilatura` (markdown + metadata) |
| Language detect | `lingua` |
| Embeddings | `sentence-transformers` (`bge-small-en-v1.5`) default · OpenAI `text-embedding-3-small` optional |
| Topic clustering | `BERTopic` (sentence-transformers → UMAP → HDBSCAN → c-TF-IDF) |
| LLM labels | configurable provider (used only for topic/category names) |
| Frontend | vanilla HTML/JS/SVG |

Keep all model/provider choices behind `config.py` so the repo runs locally with **no API keys** (local embeddings, term-based labels) and can be upgraded with keys.

---

## 12. Out of scope (future)
- **Demand & white space** — needs audience/search signal; belongs to a separate "Audience Gap" layer.
- **Topical authority** — the evolution of this map: add depth, rankings, backlinks, AI-citation signals to turn *coverage* into *authority*. Separate project.
- Background job queue / multi-tenant / auth / scheduling & monitoring of changes over time.
- Writing or recommending content.

---

## 13. Acceptance criteria (whole system)
1. Given an own domain + ≥1 competitor, a run crawls each (respecting robots + page cap), extracts clean content, and completes without manual steps.
2. Topics are discovered from the combined content (not a seed list) and have readable labels, grouped into categories.
3. Every topic has exactly one coverage state ∈ {only_you, you_lead, even, comp_lead, only_comp} and a coverage share that sums to 100%.
4. `GET /runs/{id}/map` returns the category→topic tree with states and shares.
5. `GET /runs/{id}/topics/{id}` returns the detected content per domain — real matched sentences with real source-page URLs.
6. The radial UI renders the map, colours nodes by state, and the detail panel shows detected content with working links.
7. All thresholds are config, not hardcoded. The repo runs end-to-end locally with no paid API keys.
