"""Integration test: chiron_worker.recompute against a real domain_cache table (AC2, AC3)."""

import pandas as pd
import pytest

from chiron_worker import recompute


def _sample_ohlcv_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": [pd.Timestamp("2026-08-01")],
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.0],
            "Close": [10.5],
            "Volume": [1000],
        }
    )


@pytest.mark.integration
async def test_price_recompute_writes_then_skips_on_unchanged_version(monkeypatch, cache_pool):
    df = _sample_ohlcv_df()
    monkeypatch.setattr(recompute, "load_ohlcv", lambda ticker, curr_date: df)

    await recompute.recompute_price(cache_pool, ticker="AAPL", stock="AAPL")

    async with cache_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT payload, raw_version, updated_at FROM domain_cache "
            "WHERE domain = 'price' AND stock = 'AAPL'"
        )
    assert row is not None
    assert row["payload"] == {"ohlcv": recompute._normalize_ohlcv(df)}
    first_updated_at = row["updated_at"]

    # Second tick with identical data: raw_version is unchanged, so no write happens
    # and updated_at must not move (AC2).
    await recompute.recompute_price(cache_pool, ticker="AAPL", stock="AAPL")

    async with cache_pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT updated_at FROM domain_cache WHERE domain = 'price' AND stock = 'AAPL'"
        )
    assert row["updated_at"] == first_updated_at
