"""Unit tests for chiron_worker.recompute's cache-hit/miss behavior (AC2, AC3)."""

from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pandas as pd
import pytest

from chiron_cache import compute_raw_version
from chiron_worker import recompute


def _sample_ohlcv_df() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": [pd.Timestamp("2026-08-01"), pd.Timestamp("2026-08-02")],
            "Open": [10.0, 11.0],
            "High": [11.0, 12.0],
            "Low": [9.0, 10.0],
            "Close": [10.5, 11.5],
            "Volume": [1000, 1100],
        }
    )


@asynccontextmanager
async def _fake_domain_lock(pool, domain, stock):
    yield "conn"


@pytest.mark.unit
async def test_price_recompute_cache_hit_skips_write(monkeypatch):
    """Unchanged raw_version: zero calls to write_domain_cache, no updated_at bump (AC2)."""
    df = _sample_ohlcv_df()
    ohlcv = recompute._normalize_ohlcv(df)
    raw_version = compute_raw_version(ohlcv)

    read_mock = AsyncMock(return_value={"raw_version": raw_version})
    write_mock = AsyncMock()
    monkeypatch.setattr(recompute, "load_ohlcv", lambda ticker, curr_date: df)
    monkeypatch.setattr(recompute, "read_domain_cache", read_mock)
    monkeypatch.setattr(recompute, "write_domain_cache", write_mock)
    monkeypatch.setattr(recompute, "domain_lock", _fake_domain_lock)

    await recompute.recompute_price(pool=None, ticker="AAPL", stock="AAPL")

    write_mock.assert_not_awaited()


@pytest.mark.unit
async def test_price_recompute_cache_miss_writes_inside_lock(monkeypatch):
    """Changed raw_version: write_domain_cache is called with the new payload (AC3)."""
    df = _sample_ohlcv_df()

    read_mock = AsyncMock(return_value={"raw_version": "stale-version"})
    write_mock = AsyncMock()
    monkeypatch.setattr(recompute, "load_ohlcv", lambda ticker, curr_date: df)
    monkeypatch.setattr(recompute, "read_domain_cache", read_mock)
    monkeypatch.setattr(recompute, "write_domain_cache", write_mock)
    monkeypatch.setattr(recompute, "domain_lock", _fake_domain_lock)

    await recompute.recompute_price(pool=None, ticker="AAPL", stock="AAPL")

    write_mock.assert_awaited_once()
    args = write_mock.await_args.args
    assert args[0] == "conn"
    assert args[1] == "price"
    assert args[2] == "AAPL"
    assert args[3] == {"ohlcv": recompute._normalize_ohlcv(df)}


@pytest.mark.unit
async def test_price_recompute_cache_miss_when_no_prior_row(monkeypatch):
    """No prior row at all is also a cache miss — writes rather than erroring."""
    df = _sample_ohlcv_df()

    read_mock = AsyncMock(return_value=None)
    write_mock = AsyncMock()
    monkeypatch.setattr(recompute, "load_ohlcv", lambda ticker, curr_date: df)
    monkeypatch.setattr(recompute, "read_domain_cache", read_mock)
    monkeypatch.setattr(recompute, "write_domain_cache", write_mock)
    monkeypatch.setattr(recompute, "domain_lock", _fake_domain_lock)

    await recompute.recompute_price(pool=None, ticker="AAPL", stock="AAPL")

    write_mock.assert_awaited_once()
