from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from psycopg import Connection
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from .config import settings


pool = ConnectionPool(
    conninfo=settings.database_url,
    min_size=1,
    max_size=8,
    kwargs={"row_factory": dict_row},
    open=False,
)


def open_pool() -> None:
    if pool.closed:
        pool.open()


def close_pool() -> None:
    if not pool.closed:
        pool.close()


@contextmanager
def get_conn() -> Iterator[Connection[Any]]:
    open_pool()
    with pool.connection() as conn:
        yield conn


def run_schema(schema_path: Path) -> None:
    with get_conn() as conn:
        conn.execute(schema_path.read_text())
        conn.commit()
