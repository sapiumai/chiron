"""Unit tests for chiron_cache.versioning.compute_raw_version (AC 3, 4)."""

import pytest

from chiron_cache.versioning import compute_raw_version


@pytest.mark.unit
def test_same_content_different_key_order_hashes_identically():
    a = {"symbol": "AAPL", "ohlcv": [1, 2, 3]}
    b = {"ohlcv": [1, 2, 3], "symbol": "AAPL"}
    assert compute_raw_version(a) == compute_raw_version(b)


@pytest.mark.unit
def test_changing_a_field_changes_the_hash():
    a = {"symbol": "AAPL", "ohlcv": [1, 2, 3]}
    b = {"symbol": "AAPL", "ohlcv": [1, 2, 4]}
    assert compute_raw_version(a) != compute_raw_version(b)


@pytest.mark.unit
def test_price_domain_ohlcv_shape_hashes_deterministically_across_calls():
    payload = {
        "ohlcv": [
            {
                "date": "2026-08-01",
                "open": 1.0,
                "high": 2.0,
                "low": 0.5,
                "close": 1.5,
                "volume": 100,
            },
            {
                "date": "2026-08-02",
                "open": 1.5,
                "high": 2.5,
                "low": 1.0,
                "close": 2.0,
                "volume": 200,
            },
        ]
    }
    assert compute_raw_version(payload) == compute_raw_version(payload)
    # A separately-constructed but content-identical payload (different key
    # order per row) must match too.
    rebuilt = {
        "ohlcv": [
            {
                "volume": 100,
                "close": 1.5,
                "low": 0.5,
                "high": 2.0,
                "open": 1.0,
                "date": "2026-08-01",
            },
            {
                "volume": 200,
                "close": 2.0,
                "low": 1.0,
                "high": 2.5,
                "open": 1.5,
                "date": "2026-08-02",
            },
        ]
    }
    assert compute_raw_version(payload) == compute_raw_version(rebuilt)
