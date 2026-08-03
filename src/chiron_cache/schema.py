"""Idempotent DDL for the generic ``domain_cache`` table.

No Alembic/migration tooling per epics.md's "Deferred: concrete Postgres
DDL/migration tooling" note and this project's "no persistent production
data yet" rule — see AD-4.
"""

import asyncpg

_CREATE_DOMAIN_CACHE_SQL = """
CREATE TABLE IF NOT EXISTS domain_cache (
    domain TEXT NOT NULL,
    stock TEXT NOT NULL,
    payload JSONB NOT NULL,
    raw_version TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (domain, stock)
);
"""


async def ensure_schema(conn: asyncpg.Connection) -> None:
    """Apply the ``domain_cache`` DDL. Idempotent — safe on every process start."""
    await conn.execute(_CREATE_DOMAIN_CACHE_SQL)
