"""Advisory-lock transaction helper for the ``domain_cache`` table (AD-6).

``domain_lock`` wraps a freshness read and a recompute-and-write in one
Postgres transaction, opened with
``pg_advisory_xact_lock(hashtext(domain), hashtext(stock))`` before either
touches the row. Its context-manager shape makes it structurally awkward to
split the read and the write into two separate transactions: both must
happen against the single connection/transaction the ``async with`` block
yields.

The read/write helpers below take ``stock`` as an already-normalized string
(``chiron.dataflows.symbol_utils.normalize_symbol(ticker)``) and never
re-normalize it — normalization is the caller's job. This module does not
import that function at all, so a caller passing a raw ticker is a caller
bug, not something silently corrected here.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import asyncpg


@asynccontextmanager
async def domain_lock(
    pool: asyncpg.Pool, domain: str, stock: str
) -> AsyncIterator[asyncpg.Connection]:
    """Yield a connection whose open transaction holds the ``(domain, stock)``
    advisory lock for the duration of the ``async with`` block.

    Do the freshness read and the conditional write inside this block; the
    lock is released and the transaction committed (or rolled back on
    exception) when the block exits.
    """
    async with pool.acquire() as conn, conn.transaction():
        await conn.execute(
            "SELECT pg_advisory_xact_lock(hashtext($1), hashtext($2))", domain, stock
        )
        yield conn


async def read_domain_cache(
    conn: asyncpg.Connection, domain: str, stock: str
) -> asyncpg.Record | None:
    """Read the current cache row for ``(domain, stock)``, if any.

    Must only be called inside a ``domain_lock`` transaction.
    """
    return await conn.fetchrow(
        "SELECT domain, stock, payload, raw_version, updated_at "
        "FROM domain_cache WHERE domain = $1 AND stock = $2",
        domain,
        stock,
    )


async def write_domain_cache(
    conn: asyncpg.Connection, domain: str, stock: str, payload: Any, raw_version: str
) -> None:
    """Upsert the cache row for ``(domain, stock)``.

    Stores ``stock`` exactly as given — does not re-derive or mutate it.
    Must only be called inside a ``domain_lock`` transaction.
    """
    await conn.execute(
        """
        INSERT INTO domain_cache (domain, stock, payload, raw_version, updated_at)
        VALUES ($1, $2, $3, $4, now())
        ON CONFLICT (domain, stock)
        DO UPDATE SET payload = $3, raw_version = $4, updated_at = now()
        """,
        domain,
        stock,
        payload,
        raw_version,
    )
