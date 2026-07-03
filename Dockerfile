# Homepage Language Match — single container serving the API + frontend.
FROM python:3.11-slim

WORKDIR /app

# Build deps for lxml / sentence-transformers wheels.
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential && rm -rf /var/lib/apt/lists/*

# Install Python deps first (better layer caching).
COPY pyproject.toml README.md ./
COPY backend ./backend
RUN pip install --no-cache-dir -e ".[ml]"

# Pre-download the embedding model so the first request isn't slow.
RUN python -c "from sentence_transformers import SentenceTransformer; \
    SentenceTransformer('BAAI/bge-small-en-v1.5')"

COPY frontend ./frontend

# SQLite lives here; mount a volume at /data to persist history across deploys.
ENV TC_DB_PATH=/data/app.db
RUN mkdir -p /data

# Hosts inject $PORT (Render/Fly). Default 7860 = Hugging Face Spaces' port.
ENV PORT=7860
CMD ["sh", "-c", "uvicorn backend.app:app --host 0.0.0.0 --port ${PORT}"]
