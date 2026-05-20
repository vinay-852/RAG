from __future__ import annotations

import json
from urllib.parse import urljoin

import requests
from openai import OpenAI

from .config import settings


def _headers() -> dict[str, str]:
    headers = {
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
        "client": settings.llm_client_name,
        "client-version": settings.llm_client_version,
    }
    if settings.llm_api_key:
        headers["Authorization"] = f"Bearer {settings.llm_api_key}"
    return headers


def _chat_completions_url() -> str:
    base = settings.llm_base_url.rstrip("/") + "/"
    return urljoin(base, settings.llm_completions_path.lstrip("/"))


def uses_oca_adapter() -> bool:
    model = settings.llm_model.lower()
    base_url = settings.llm_base_url.lower()
    return model.startswith("oca/") or "oraclecloud.com" in base_url or "/app/litellm" in base_url


def parse_streaming_completion(completion: str) -> str:
    result = ""
    for line in completion.splitlines():
        if not line.startswith("data:"):
            continue

        line = line.replace("data:", "", 1).strip()
        if line == "[DONE]":
            break

        chunk = json.loads(line)
        content = chunk["choices"][0]["delta"].get("content", "")
        result += content
    return result


def oca_completion(messages: list[dict[str, str]]) -> str:
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "stream": True,
    }
    response = requests.post(
        _chat_completions_url(),
        headers=_headers(),
        json=payload,
        timeout=120,
    )
    response.raise_for_status()

    stream_text = response.text
    parsed = parse_streaming_completion(stream_text)
    if parsed:
        return parsed

    data = response.json()
    return data["choices"][0]["message"]["content"]


def normal_completion(messages: list[dict[str, str]]) -> str:
    client = OpenAI(api_key=settings.llm_api_key)
    response = client.responses.create(
        model=settings.llm_model or settings.chat_model,
        input=messages,
    )
    return response.output_text


def completion(messages: list[dict[str, str]]) -> str:
    if uses_oca_adapter():
        return oca_completion(messages)
    return normal_completion(messages)
