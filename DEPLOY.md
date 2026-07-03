# Deploying Homepage Language Match

The app is one FastAPI service that also serves the frontend, so you deploy a
single container and get one public URL. The LLM uses an OpenAI-compatible
endpoint (default: **Groq**, free tier) — set as env vars on the host, never
committed.

## Option A — quick shareable link today (no deploy)
Run locally and expose it with a tunnel:

```bash
make dev                      # serves on http://localhost:8000
# in another terminal:
ngrok http 8000               # or: cloudflared tunnel --url http://localhost:8000
```

ngrok prints a public `https://…` URL your friend can open. It's live only while
your laptop + `make dev` are running.

## Option B — persistent deploy (Render)
1. Push this repo to GitHub.
2. On [render.com](https://render.com): **New → Blueprint**, point it at the repo.
   `render.yaml` provisions a Docker web service with a 1 GB disk for history.
3. In the service's **Environment**, set `TC_LLM_API_KEY` to your Groq key
   (`gsk_…` from console.groq.com). The base URL + model are already set.
4. Deploy. Render builds the `Dockerfile` and gives you a
   `https://homepage-language-match.onrender.com` URL.

**RAM:** the embedding model needs ~1 GB, so use the **Starter** plan (the free
512 MB tier can OOM). To go lighter/free, set the LLM off and swap the embedding
model, or host the embeddings via an API.

## Option C — Fly.io
```bash
fly launch --dockerfile Dockerfile --no-deploy   # generates fly.toml
fly volumes create data --size 1                  # persist /data
fly secrets set TC_LLM_API_KEY=gsk_...            # + base url / model
fly deploy
```

## Run the container locally (to test the image)
```bash
docker build -t hlm .
docker run -p 8000:8000 \
  -e TC_LLM_BASE_URL=https://api.groq.com/openai/v1 \
  -e TC_LLM_MODEL=llama-3.1-8b-instant \
  -e TC_LLM_API_KEY=gsk_your_key \
  hlm
```

## Notes
- **No LLM key?** It still works — the deterministic explanation is used.
- **Secrets:** only ever set keys as host env vars / dashboard secrets. `.env` is
  gitignored; nothing secret is in the repo.
- **History:** stored in SQLite at `/data/app.db`; mount a volume (as above) to
  keep it across deploys, otherwise it resets each deploy.
