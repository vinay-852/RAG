from __future__ import annotations

from .config import settings
from .llm_client import completion
from .retrieval import Source
from .router import RouteDecision
from .security import UserContext


def _source_block(sources: list[Source]) -> str:
    lines = []
    for idx, source in enumerate(sources, start=1):
        lines.append(
            f"[{idx}] type={source.source_type} title={source.title} score={source.score:.3f}\n"
            f"{source.content}\n"
            f"metadata={source.metadata}"
        )
    return "\n\n".join(lines)


def generate_answer(
    question: str,
    user: UserContext,
    route: RouteDecision,
    sources: list[Source],
    sql_summary: str | None = None,
) -> str:
    if not sources and not sql_summary:
        return "I could not find authorized context for this user. No answer was generated."

    context = sql_summary or _source_block(sources)
    if not settings.llm_api_key:
        cited = "\n".join(f"- [{idx}] {source.title}: {source.content[:240]}" for idx, source in enumerate(sources, start=1))
        prefix = f"Route: {route.route.value} ({route.reason}).\n"
        return prefix + (sql_summary or cited)

    return completion(
        [
            {
                "role": "system",
                "content": (
                    "You are an enterprise RAG assistant. Answer only from the provided authorized context. "
                    "If the context is insufficient, say so. Cite sources with bracket numbers like [1]. "
                    "Never reveal inaccessible data or speculate about hidden rows."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User: {user.display_name}\n"
                    f"Roles: {', '.join(user.roles)}\n"
                    f"Route: {route.route.value}; reason: {route.reason}; confidence: {route.confidence:.2f}\n"
                    f"Question: {question}\n\nAuthorized context:\n{context}"
                ),
            },
        ]
    )
