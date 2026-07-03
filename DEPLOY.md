# Deploying Homepage Language Match

The app is one FastAPI service that also serves the frontend, so you deploy it
once and get one public URL. The LLM uses an OpenAI-compatible endpoint
(default: **Groq**, free tier) — set as env vars on the host, never committed.

> **Not Netlify.** Netlify only hosts static sites + small JS functions; this has
> a Python + ML backend, so it needs a Python host. The good news: **no Docker
> required** — the hosts below build from your GitHub repo. Pick one:

## Easiest — Render, no Docker (recommended)
1. Push this repo to GitHub.
2. On [render.com](https://render.com): **New → Blueprint** → pick the repo.
   `render.yaml` sets everything (build/start commands, disk, env).
3. In **Environment**, set `TC_LLM_API_KEY` to your Groq key (`gsk_…`).
4. Deploy → you get a `https://…onrender.com` URL. (Starter plan ~$7/mo for the
   RAM the model needs.)

## Free — Hugging Face Spaces (great for ML, generous RAM)
1. Create a **Space** → SDK: **Docker** → push this repo (HF builds the
   `Dockerfile` for you; no local Docker needed).
2. In the Space **Settings → Variables and secrets**, set `TC_LLM_BASE_URL`,
   `TC_LLM_MODEL`, and secret `TC_LLM_API_KEY`.
3. It builds and gives you a public `…hf.space` URL. Free CPU tier has plenty of
   RAM for the embedding model.

## Option A — quick shareable link today (no deploy)
Run locally and expose it with a tunnel:

```bash
make dev                      # serves on http://localhost:8000
# in another terminal:
ngrok http 8000               # or: cloudflared tunnel --url http://localhost:8000
```

ngrok prints a public `https://…` URL your friend can open. It's live only while
your laptop + `make dev` are running.

## Also fine — Fly.io or a Docker host
A `Dockerfile` is included if you prefer a container host (Fly.io, a VPS, etc.):
```bash
fly launch --no-deploy && fly volumes create data --size 1
fly secrets set TC_LLM_API_KEY=gsk_...            # + base url / model
fly deploy
```

## Notes
- **No LLM key?** It still works — the deterministic explanation is used.
- **Secrets:** only ever set keys as host env vars / dashboard secrets. `.env` is
  gitignored; nothing secret is in the repo.
- **History:** stored in SQLite at `/data/app.db`; mount a volume (as above) to
  keep it across deploys, otherwise it resets each deploy.
