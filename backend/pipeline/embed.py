"""Text embeddings for the semantic similarity score.

Local by default (sentence-transformers, no key); optionally a hosted backend
(OpenAI) behind config. Vectors are L2-normalised so cosine == dot product.
"""
from __future__ import annotations

from typing import List

import numpy as np

from ..config import Config, config


class _LocalEmbedder:
    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer

        self.model = SentenceTransformer(model_name)

    def encode(self, texts: List[str]) -> np.ndarray:
        vecs = self.model.encode(
            texts, batch_size=32, normalize_embeddings=True, show_progress_bar=False,
        )
        return np.asarray(vecs, dtype=np.float32)


class _OpenAIEmbedder:
    def __init__(self, api_key: str, model: str = "text-embedding-3-small"):
        from openai import OpenAI

        self.client = OpenAI(api_key=api_key)
        self.model = model

    def encode(self, texts: List[str]) -> np.ndarray:
        resp = self.client.embeddings.create(model=self.model, input=texts)
        vecs = np.asarray([d.embedding for d in resp.data], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return vecs / norms


_EMBEDDER = None


def get_embedder(cfg: Config = config):
    """Return a cached embedder for the configured backend."""
    global _EMBEDDER
    if _EMBEDDER is not None:
        return _EMBEDDER
    if cfg.embedding_backend == "openai" and cfg.openai_api_key:
        _EMBEDDER = _OpenAIEmbedder(cfg.openai_api_key)
    else:
        _EMBEDDER = _LocalEmbedder(cfg.local_embedding_model)
    return _EMBEDDER


def embed_texts(texts: List[str], cfg: Config = config) -> np.ndarray:
    if not texts:
        return np.zeros((0, 0), dtype=np.float32)
    return get_embedder(cfg).encode(texts)
