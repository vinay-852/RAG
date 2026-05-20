from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[1]


@dataclass(frozen=True)
class Settings:
    database_url: str = os.getenv(
        "DATABASE_URL",
        "postgresql://rag_app:rag_app@localhost:5432/enterprise_rag",
    )
    openai_api_key: str | None = os.getenv("OPENAI_API_KEY")
    llm_api_key: str | None = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    llm_base_url: str = os.getenv(
        "LLM_BASE_URL",
        "https://code-internal.aiservice.us-chicago-1.oci.oraclecloud.com/20250206/app/litellm",
    )
    llm_completions_path: str = os.getenv("LLM_COMPLETIONS_PATH", "chat/completions")
    llm_model: str = os.getenv("LLM_MODEL", "oca/gpt5")
    llm_client_name: str = os.getenv("LLM_CLIENT_NAME", "codex-cli")
    llm_client_version: str = os.getenv("LLM_CLIENT_VERSION", "0")
    chat_model: str = os.getenv("OPENAI_CHAT_MODEL", "gpt-4.1-mini")
    embedding_model: str = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    embedding_dimensions: int = int(os.getenv("EMBEDDING_DIMENSIONS", "1536"))
    chunk_size: int = int(os.getenv("CHUNK_SIZE", "1200"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "150"))
    cors_origin: str = os.getenv("CORS_ORIGIN", "*")


settings = Settings()
