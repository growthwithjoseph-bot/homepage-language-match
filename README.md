---
title: Homepage Language Match
emoji: 🔤
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
pinned: false
---

# 🔤 Homepage Language Match

### Are you *differentiated* — or just saying the same thing as everyone else?

![Python](https://img.shields.io/badge/Python-3.9%2B-3776AB?logo=python&logoColor=white)
![Deterministic](https://img.shields.io/badge/scores-deterministic-15803d)
![Runs local](https://img.shields.io/badge/runs-100%25%20local-22c55e)
![No API keys](https://img.shields.io/badge/API%20keys-optional-6366f1)

Enter **your domain and up to 5 competitors**. Homepage Language Match reads each
**homepage** — the single most fought-over page you own — pulls out its
**headlines** and **paragraphs**, and scores how close your messaging is to each
rival's, on two axes:

- 🧠 **Meaning (semantic)** — are you saying the *same things*, even in different words?
- 🔡 **Wording (lexical)** — are you using the *same actual words and phrases*?

…for headlines and paragraphs — four **0–100 scores** per competitor — plus an
optional AI-written explanation of *why*.

---

## 💡 Why it matters (the business value)

Most homepages in a category drift toward the **same tired language**: "the
all-in-one platform," "supercharge your workflow," "trusted by teams worldwide."
When you sound like everyone else, you're **invisible** — buyers can't tell you
apart, and you compete on price instead of value.

Homepage Language Match is a **sea-of-sameness detector**:

| The problem 😵‍💫 | What this gives you ✅ |
|---|---|
| "Do we actually sound different?" — nobody knows | A number: how close you are to each rival, by meaning *and* words |
| Positioning debates run on opinion | Evidence you can put in front of the team |
| Copywriters guess what's "generic" | A clear read on where you blend in vs. stand out |
| Rebrands launch on vibes | A before/after you can measure |

**Read it like this:**
- 🔴 **High similarity** → you're echoing a competitor — a differentiation risk.
- 🟢 **Low similarity** → you've carved out distinct language — a positioning asset.

**Who it's for:** 🚀 founders & positioning owners · ✍️ brand and content strategists
· 📣 product marketers · 🏢 agencies pitching a sharper message.

---

## ✨ What you get

- 🎯 **Per-competitor score cards** — meaning & wording, headlines & paragraphs, at a glance.
- 🗺️ **A meaning-vs-wording scatter** — instantly see who you're closest to (and how).
- 🤖 **An optional "why"** — a short, plain-English read on *what* makes you similar or different.
- 🕘 **Search history** — revisit past comparisons.
- 🔒 **Deterministic & private** — same input → same score, computed locally. No accounts.

---

## ⚙️ How it works (one line)

**fetch each homepage → extract headlines + paragraphs → embed locally → compute deterministic semantic + lexical scores (you vs each competitor) → optional AI "why" → cards + scatter.**

Homepage-only by design — fast, focused, and about *messaging*, not SEO.

---

## 🚀 Quickstart

```bash
git clone https://github.com/growthwithjoseph-bot/homepage-language-match.git
cd homepage-language-match
python3 -m venv .venv && source .venv/bin/activate
make install-ml          # deps incl. the local embedding model
make dev                 # FastAPI + UI on http://localhost:8000
```

Open **http://localhost:8000**, enter your domain and competitors, hit **Compare**.
Or via the API:

```bash
curl -X POST localhost:8000/runs \
  -H 'content-type: application/json' \
  -d '{"own_domain":"fathom.ai","competitor_domains":["otter.ai","fireflies.ai"]}'
# then poll GET /runs/{id} until "done", and read GET /runs/{id}/report
```

---

## 🧠 Under the hood

Scores use **local embeddings** (`sentence-transformers`) — no key needed, and
fully **deterministic**. The AI "why" is **optional and provider-agnostic** (one
OpenAI-compatible client): point it at local **Ollama** or a free **Groq** key via
`TC_LLM_BASE_URL` / `TC_LLM_MODEL` / `TC_LLM_API_KEY`; if unset, a deterministic
explanation is used. Secrets live only in a gitignored `.env`.

See **`SPEC.md`** for the full spec, **`CLAUDE.md`** for conventions, **`DEPLOY.md`**
to put it online.

---

## 🧩 Part of a small toolkit for understanding markets

- 🔤 **Homepage Language Match** *(this repo)* — is your messaging differentiated, or an echo?
- 🕸️ **[Topic Coverage](https://github.com/growthwithjoseph-bot/topic-coverage)** — who covers which topics across the whole site, and who covers them more
- 💬 **[Anatomy of a Brand Conversation](https://growthwithjoseph-bot.github.io/hubspot-brand-conversation/)** — how real people talk about a brand across the internet
