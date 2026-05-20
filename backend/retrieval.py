from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pgvector.psycopg import register_vector

from .db import get_conn
from .embeddings import embedder
from .security import UserContext


@dataclass(frozen=True)
class Source:
    source_type: str
    title: str
    content: str
    score: float
    metadata: dict[str, Any]


def _params(user: UserContext) -> dict[str, Any]:
    return {"tenant_id": user.tenant_id, "roles": user.roles}


def search_documents(question: str, user: UserContext, limit: int = 5) -> list[Source]:
    vector = embedder.embed(question)
    with get_conn() as conn:
        register_vector(conn)
        rows = conn.execute(
            """
            SELECT
                d.title,
                d.source_uri,
                d.source_type,
                c.content,
                c.metadata,
                1 - (c.embedding <=> %(embedding)s) AS score
            FROM document_chunks c
            JOIN documents d ON d.id = c.document_id
            WHERE c.tenant_id = %(tenant_id)s
              AND c.allowed_roles && %(roles)s::text[]
            ORDER BY c.embedding <=> %(embedding)s
            LIMIT %(limit)s
            """,
            {**_params(user), "embedding": vector, "limit": limit},
        ).fetchall()
    return [
        Source("document", row["title"], row["content"], float(row["score"]), {**row["metadata"], "source_uri": row["source_uri"], "source_type": row["source_type"]})
        for row in rows
    ]


def search_events(question: str, user: UserContext, limit: int = 5) -> list[Source]:
    vector = embedder.embed(question)
    with get_conn() as conn:
        register_vector(conn)
        rows = conn.execute(
            """
            SELECT
                service,
                level,
                event_ts,
                action,
                resource,
                message,
                raw,
                1 - (embedding <=> %(embedding)s) AS score
            FROM event_logs
            WHERE tenant_id = %(tenant_id)s
              AND allowed_roles && %(roles)s::text[]
            ORDER BY embedding <=> %(embedding)s
            LIMIT %(limit)s
            """,
            {**_params(user), "embedding": vector, "limit": limit},
        ).fetchall()
    return [
        Source(
            "event",
            f"{row['service']} {row['level']} {row['event_ts']}",
            row["message"],
            float(row["score"]),
            {"service": row["service"], "level": row["level"], "action": row["action"], "resource": row["resource"], "raw": row["raw"]},
        )
        for row in rows
    ]


def search_audits(question: str, user: UserContext, limit: int = 5) -> list[Source]:
    with get_conn() as conn:
        rows = conn.execute(
            """
            SELECT event_ts, actor, action, object_type, object_id, before_value, after_value, reason
            FROM audit_events
            WHERE tenant_id = %(tenant_id)s
              AND allowed_roles && %(roles)s::text[]
              AND (
                  actor ILIKE %(like)s
                  OR action ILIKE %(like)s
                  OR object_type ILIKE %(like)s
                  OR object_id ILIKE %(like)s
                  OR coalesce(reason, '') ILIKE %(like)s
              )
            ORDER BY event_ts DESC
            LIMIT %(limit)s
            """,
            {**_params(user), "like": f"%{question[:80]}%", "limit": limit},
        ).fetchall()
        if not rows:
            rows = conn.execute(
                """
                SELECT event_ts, actor, action, object_type, object_id, before_value, after_value, reason
                FROM audit_events
                WHERE tenant_id = %(tenant_id)s
                  AND allowed_roles && %(roles)s::text[]
                ORDER BY event_ts DESC
                LIMIT %(limit)s
                """,
                {**_params(user), "limit": limit},
            ).fetchall()
    return [
        Source(
            "audit",
            f"{row['action']} {row['object_type']} {row['object_id']}",
            f"{row['actor']} performed {row['action']} on {row['object_type']} {row['object_id']}. Reason: {row['reason'] or 'not recorded'}.",
            1.0,
            {"event_ts": row["event_ts"], "before": row["before_value"], "after": row["after_value"]},
        )
        for row in rows
    ]


def query_records(question: str, user: UserContext, limit: int = 8) -> tuple[str, list[Source]]:
    q = question.lower()
    with get_conn() as conn:
        if "count" in q or "how many" in q:
            rows = conn.execute(
                """
                SELECT record_type, status, count(*) AS count
                FROM enterprise_records
                WHERE tenant_id = %(tenant_id)s
                  AND allowed_roles && %(roles)s::text[]
                GROUP BY record_type, status
                ORDER BY count DESC
                """,
                _params(user),
            ).fetchall()
            summary = "\n".join(f"{row['record_type']} / {row['status']}: {row['count']}" for row in rows)
        elif "sum" in q or "total" in q or "revenue" in q or "amount" in q:
            rows = conn.execute(
                """
                SELECT business_unit, fiscal_quarter, sum(amount) AS total_amount
                FROM enterprise_records
                WHERE tenant_id = %(tenant_id)s
                  AND allowed_roles && %(roles)s::text[]
                  AND amount IS NOT NULL
                GROUP BY business_unit, fiscal_quarter
                ORDER BY fiscal_quarter DESC, total_amount DESC
                LIMIT %(limit)s
                """,
                {**_params(user), "limit": limit},
            ).fetchall()
            summary = "\n".join(f"{row['business_unit']} {row['fiscal_quarter']}: {row['total_amount']}" for row in rows)
        else:
            rows = conn.execute(
                """
                SELECT record_type, business_unit, status, amount, summary, payload, created_at
                FROM enterprise_records
                WHERE tenant_id = %(tenant_id)s
                  AND allowed_roles && %(roles)s::text[]
                  AND (
                      summary ILIKE %(like)s
                      OR record_type ILIKE %(like)s
                      OR business_unit ILIKE %(like)s
                      OR status ILIKE %(like)s
                  )
                ORDER BY created_at DESC
                LIMIT %(limit)s
                """,
                {**_params(user), "like": f"%{question[:80]}%", "limit": limit},
            ).fetchall()
            summary = "\n".join(f"{row['record_type']} {row['business_unit']} {row['status']}: {row['summary']}" for row in rows)
    sources = [
        Source(
            "sql",
            f"{row.get('record_type', 'aggregate')} {row.get('business_unit', '')}".strip(),
            str(dict(row)),
            1.0,
            {"table": "enterprise_records"},
        )
        for row in rows
    ]
    return summary or "No authorized SQL rows matched.", sources
