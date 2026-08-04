"""Shared cache-lookup helper for Analyst Nodes (AD-13 retrofit).

Bridges the synchronous analyst node functions into ``chiron_cache``'s async
API. Every call creates a fresh pool, does the lock+read, then closes the
pool — see Story 1.4's Dev Notes for why this on-demand approach (rather
than a shared pool threaded through ``graph/setup.py``) is the deliberate
choice for v1.
"""

import asyncio
import logging

from chiron_cache import create_pool, domain_lock, read_domain_cache

logger = logging.getLogger(__name__)


async def _fetch_cached_payload(domain: str, stock: str) -> dict | None:
    pool = await create_pool()
    try:
        async with domain_lock(pool, domain, stock) as conn:
            row = await read_domain_cache(conn, domain, stock)
            return dict(row["payload"]) if row else None
    finally:
        await pool.close()


def get_cached_payload(domain: str, stock: str) -> dict | None:
    """Return the cached payload for ``(domain, stock)``, or ``None`` on a miss.

    ``stock`` must already be normalized via
    ``chiron.dataflows.symbol_utils.normalize_symbol`` — this helper never
    normalizes internally. Any failure to reach the cache (missing DSN,
    connection error, missing table, etc.) is treated as a miss so callers
    always fall back to their existing live-tool path instead of crashing.
    """
    try:
        return asyncio.run(_fetch_cached_payload(domain, stock))
    except Exception:
        logger.warning(
            "Cache lookup failed for domain=%r stock=%r; falling back to live path",
            domain,
            stock,
            exc_info=True,
        )
        return None
