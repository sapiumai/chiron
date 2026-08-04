"""Connection pool creation for the domain cache.

Reads connection settings directly via ``os.environ`` — this package must
not import ``chiron.dataflows.config``/``DEFAULT_CONFIG`` (see architecture
spine, AD-9: the cache layer is pure Postgres + config, with no dependency
on chiron-specific upstream modules).
"""

import json
import os

import asyncpg


def _resolve_dsn() -> str:
    """Return the Postgres DSN, preferring an explicit override.

    ``TRADINGAGENTS_POSTGRES_DSN``, if set, wins outright (needed for
    connection details a host/port/user/password/db tuple can't express,
    e.g. ``sslmode`` or a unix socket). Otherwise the DSN is composed from
    ``POSTGRES_USER``/``POSTGRES_PASSWORD``/``POSTGRES_DB`` (the same vars
    the docker-compose ``postgres`` service is configured from) plus
    ``POSTGRES_HOST``/``POSTGRES_PORT`` (defaulting to ``localhost``/
    ``5432`` for host development) — one source of truth instead of two
    independently-set connection strings that can drift apart.
    """
    dsn = os.environ.get("TRADINGAGENTS_POSTGRES_DSN")
    if dsn:
        return dsn

    user = os.environ.get("POSTGRES_USER")
    password = os.environ.get("POSTGRES_PASSWORD")
    db = os.environ.get("POSTGRES_DB")
    if not (user and password and db):
        raise RuntimeError(
            "Neither TRADINGAGENTS_POSTGRES_DSN nor all of POSTGRES_USER/"
            "POSTGRES_PASSWORD/POSTGRES_DB are set — see .env.example for "
            "the expected format."
        )
    host = os.environ.get("POSTGRES_HOST", "localhost")
    port = os.environ.get("POSTGRES_PORT", "5432")
    return f"postgresql://{user}:{password}@{host}:{port}/{db}"


async def _init_connection(conn: asyncpg.Connection) -> None:
    await conn.set_type_codec(
        "jsonb",
        encoder=json.dumps,
        decoder=json.loads,
        schema="pg_catalog",
    )


async def create_pool() -> asyncpg.Pool:
    """Create an asyncpg connection pool for the domain cache.

    Every connection in the pool decodes ``jsonb`` columns to/from native
    Python objects, so ``read_domain_cache``/``write_domain_cache`` callers
    work with plain dicts/lists rather than raw JSON strings.
    """
    return await asyncpg.create_pool(_resolve_dsn(), init=_init_connection)
