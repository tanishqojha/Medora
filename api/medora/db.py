"""Postgres access. One pool, dict rows. Every query takes hospital_id explicitly."""
from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache
from typing import Any

import psycopg
from psycopg.rows import DictRow, dict_row
from psycopg_pool import ConnectionPool

from medora.config import database_url

Conn = psycopg.Connection[DictRow]


@lru_cache
def pool() -> ConnectionPool[Conn]:
    return ConnectionPool(
        database_url(),
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row, "autocommit": False},
        configure=_configure,
        open=True,
    )


def _configure(conn: Conn) -> None:
    # Dates are hospital-local (IST). Session settings via SET work through the Supabase session pooler.
    try:
        conn.execute("SET TIME ZONE 'Asia/Kolkata'")
    except psycopg.Error:  # builds without a tz database (embedded test Postgres): same offset, IST has no DST
        conn.rollback()
        conn.execute("SET TIME ZONE INTERVAL '+05:30' HOUR TO MINUTE")
    conn.commit()


@contextmanager
def tx() -> Iterator[Conn]:
    """A connection inside one transaction. Commits on success, rolls back on error."""
    with pool().connection() as conn:
        yield conn


def one(conn: Conn, query: str, params: Any = None) -> DictRow:
    """fetchone for rows that must exist (RETURNING, FK lookups). A missing row is a bug, not a None."""
    row = conn.execute(query, params).fetchone()  # type: ignore[arg-type]
    if row is None:
        raise LookupError(f"expected a row: {query.split()[0:4]}")
    return row
