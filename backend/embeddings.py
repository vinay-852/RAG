from __future__ import annotations

import hashlib
import math

from .config import settings


class Embedder:
    def __init__(self) -> None:
        self._client = self._build_client()

    def embed(self, text: str) -> list[float]:
        if self._client:
            response = self._client.embeddings.create(
                model=settings.embedding_model,
                input=text,
            )
            return self._fit_dimensions(response.data[0].embedding)
        return self._local_embedding(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if self._client:
            response = self._client.embeddings.create(
                model=settings.embedding_model,
                input=texts,
            )
            return [self._fit_dimensions(item.embedding) for item in response.data]
        return [self._local_embedding(text) for text in texts]

    def _build_client(self):
        provider = settings.embedding_provider
        if provider in {"groq", "grqoq"} and settings.groq_api_key:
            from openai import OpenAI

            return OpenAI(
                api_key=settings.groq_api_key,
                base_url=settings.groq_base_url.rstrip("/"),
            )
        if settings.openai_api_key:
            from openai import OpenAI

            return OpenAI(api_key=settings.openai_api_key)
        return None

    def _fit_dimensions(self, embedding: list[float]) -> list[float]:
        dims = settings.embedding_dimensions
        if len(embedding) == dims:
            return embedding
        if len(embedding) > dims:
            return embedding[:dims]
        return embedding + [0.0] * (dims - len(embedding))

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
