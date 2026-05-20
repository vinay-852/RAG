from __future__ import annotations

import hashlib
import math

from openai import OpenAI

from .config import settings


class Embedder:
    def __init__(self) -> None:
        self._client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    def embed(self, text: str) -> list[float]:
        if self._client:
            response = self._client.embeddings.create(
                model=settings.embedding_model,
                input=text,
            )
            return response.data[0].embedding
        return self._local_embedding(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._client:
            response = self._client.embeddings.create(
                model=settings.embedding_model,
                input=texts,
            )
            return [item.embedding for item in response.data]
        return [self._local_embedding(text) for text in texts]

    def _local_embedding(self, text: str) -> list[float]:
        """Deterministic offline embedding for demos without an API key."""
        dims = settings.embedding_dimensions
        vector = [0.0] * dims
        tokens = text.lower().split()
        for token in tokens:
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            bucket = int.from_bytes(digest[:4], "big") % dims
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[bucket] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


embedder = Embedder()
