from __future__ import annotations

import hashlib
import math

from .config import settings


class Embedder:
    def __init__(self) -> None:
        self._client = self._build_client()

    def embed(self, text: str) -> list[float]:
        if settings.embedding_provider == "gemini" and settings.gemini_api_key:
            return self._gemini_embed(text)
        if self._client:
            try:
                response = self._client.embeddings.create(
                    model=settings.embedding_model,
                    input=text,
                )
                return self._fit_dimensions(response.data[0].embedding)
            except Exception as exc:
                print(f"Embedding provider failed; using local fallback: {exc}")
        return self._local_embedding(text)

    def embed_many(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if settings.embedding_provider == "gemini" and settings.gemini_api_key:
            return [self._gemini_embed(text) for text in texts]
        if self._client:
            try:
                response = self._client.embeddings.create(
                    model=settings.embedding_model,
                    input=texts,
                )
                return [self._fit_dimensions(item.embedding) for item in response.data]
            except Exception as exc:
                print(f"Embedding provider failed; using local fallback: {exc}")
        return [self._local_embedding(text) for text in texts]

    def _build_client(self):
        if settings.openai_api_key:
            from openai import OpenAI

            return OpenAI(api_key=settings.openai_api_key)
        return None

    def _gemini_embed(self, text: str) -> list[float]:
        import requests

        model = settings.embedding_model.removeprefix("models/")
        model_path = f"models/{model}"
        url = f"{settings.gemini_base_url.rstrip('/')}/{model_path}:embedContent"
        response = requests.post(
            url,
            headers={
                "Content-Type": "application/json",
                "X-goog-api-key": settings.gemini_api_key or "",
            },
            json={
                "model": model_path,
                "content": {"parts": [{"text": text}]},
                "outputDimensionality": settings.embedding_dimensions,
            },
            timeout=60,
        )
        try:
            response.raise_for_status()
            return self._fit_dimensions(response.json()["embedding"]["values"])
        except Exception as exc:
            print(f"Gemini embedding failed; using local fallback: {exc}")
            return self._local_embedding(text)

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
