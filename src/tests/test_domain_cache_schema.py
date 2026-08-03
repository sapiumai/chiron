"""Integration test for the domain_cache DDL (AC 1)."""

import asyncpg
import pytest


@pytest.mark.integration
async def test_domain_cache_has_expected_columns_and_composite_pk(cache_pool):
    async with cache_pool.acquire() as conn:
        columns = await conn.fetch(
            """
            SELECT column_name FROM information_schema.columns
            WHERE table_name = 'domain_cache'
            """
        )
        column_names = {row["column_name"] for row in columns}
        assert column_names == {"domain", "stock", "payload", "raw_version", "updated_at"}

        await conn.execute(
            "INSERT INTO domain_cache (domain, stock, payload, raw_version) "
            "VALUES ('price', 'AAPL', '{}', 'v1')"
        )
        with pytest.raises(asyncpg.UniqueViolationError):
            await conn.execute(
                "INSERT INTO domain_cache (domain, stock, payload, raw_version) "
                "VALUES ('price', 'AAPL', '{}', 'v2')"
            )
