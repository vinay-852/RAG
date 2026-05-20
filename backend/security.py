from __future__ import annotations

from dataclasses import dataclass

from .db import get_conn


@dataclass(frozen=True)
class UserContext:
    user_id: str
    email: str
    display_name: str
    department: str
    tenant_id: str
    roles: list[str]


def get_user_context(user_id: str) -> UserContext:
    with get_conn() as conn:
        row = conn.execute(
            """
            SELECT
                u.id,
                u.email,
                u.display_name,
                u.department,
                u.tenant_id,
                coalesce(array_agg(ur.role_id) FILTER (WHERE ur.role_id IS NOT NULL), '{}') AS roles
            FROM app_users u
            LEFT JOIN user_roles ur ON ur.user_id = u.id
            WHERE u.id = %s
            GROUP BY u.id
            """,
            (user_id,),
        ).fetchone()
    if not row:
        raise ValueError(f"Unknown user: {user_id}")
    return UserContext(
        user_id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        department=row["department"],
        tenant_id=row["tenant_id"],
        roles=list(row["roles"] or []),
    )


def role_filter_sql(alias: str = "") -> str:
    prefix = f"{alias}." if alias else ""
    return f"{prefix}tenant_id = %(tenant_id)s AND {prefix}allowed_roles && %(roles)s::text[]"
