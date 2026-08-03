"""Connection pool creation for the domain cache.

Reads ``TRADINGAGENTS_POSTGRES_DSN`` directly via ``os.environ`` — this
package must not import ``chiron.dataflows.config``/``DEFAULT_CONFIG``
(see architecture spine, AD-9: the cache layer is pure Postgres + config,
with no dependency on chiron-specific upstream modules).
"""

import json
import os

import asyncpg


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def create_pool() -> asyncpg.Pool:
    """Create an asyncpg connection pool from ``TRADINGAGENTS_POSTGRES_DSN``.

    Every connection in the pool decodes ``jsonb`` columns to/from native
    Python objects, so ``read_domain_cache``/``write_domain_cache`` callers
    work with plain dicts/lists rather than raw JSON strings.
    """
    dsn = os.environ.get("TRADINGAGENTS_POSTGRES_DSN")
    if not dsn:
        raise RuntimeError(
            "TRADINGAGENTS_POSTGRES_DSN is not set — see .env.example for the "
            "expected format."
        )
    return await asyncpg.create_pool(dsn, init=_init_connection)
