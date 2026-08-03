"""Unit tests for chiron_worker.recompute's News Domain path (AC2, AC3, AC5)."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from chiron_worker import recompute
from chiron_worker.rate_limiter import VendorRateLimiter

_NEWS_JSON = json.dumps(
    {
        "feed": [
            {
                "time_published": "20260801T093000",
                "ticker_sentiment": [
                    {
                        "ticker": "AAPL",
                        "relevance_score": "0.85",
                        "ticker_sentiment_score": "0.4",
                        "ticker_sentiment_label": "Bullish",
                    },
                    {
                        "ticker": "MSFT",
                        "relevance_score": "0.2",
                        "ticker_sentiment_score": "0.1",
                        "ticker_sentiment_label": "Neutral",
                    },
                ],
            }
        ]
    }
)


@asynccontextmanager
async def _fake_domain_lock(pool, domain, stock):
    yield "conn"


def test_normalize_news_extracts_only_matching_ticker_signals():
    payload = recompute._normalize_news(_NEWS_JSON, "AAPL")
    assert payload["signals"] == [
        {
            "entity": "AAPL",
            "tendency": "up",
            "confidence": 0.85,
            "as_of": "2026-08-01T09:30:00",
        }
    ]


def test_tendency_from_label_maps_bullish_bearish_neutral():
    assert recompute._tendency_from_label("Somewhat-Bullish") == "up"
    assert recompute._tendency_from_label("Somewhat-Bearish") == "down"
    assert recompute._tendency_from_label("Neutral") == "neutral"
    assert recompute._tendency_from_label(None) == "neutral"


@pytest.mark.unit
async def test_news_recompute_writes_when_changed(monkeypatch):
    write_mock = AsyncMock()
    monkeypatch.setattr(recompute, "get_news", lambda ticker, start, end: _NEWS_JSON)
    monkeypatch.setattr(recompute, "read_domain_cache", AsyncMock(return_value=None))
    monkeypatch.setattr(recompute, "write_domain_cache", write_mock)
    monkeypatch.setattr(recompute, "domain_lock", _fake_domain_lock)

    limiter = VendorRateLimiter({"alpha_vantage": 10})
    await recompute.recompute_news(pool=None, ticker="AAPL", stock="AAPL", rate_limiter=limiter)

    write_mock.assert_awaited_once()


@pytest.mark.unit
async def test_news_recompute_skips_tick_when_cap_exhausted(monkeypatch):
    fetch_mock = AsyncMock()
    monkeypatch.setattr(recompute, "get_news", lambda ticker, start, end: fetch_mock())
    write_mock = AsyncMock()
    monkeypatch.setattr(recompute, "write_domain_cache", write_mock)
    monkeypatch.setattr(recompute, "domain_lock", _fake_domain_lock)

    limiter = VendorRateLimiter({"alpha_vantage": 0})
    await recompute.recompute_news(pool=None, ticker="AAPL", stock="AAPL", rate_limiter=limiter)

    fetch_mock.assert_not_called()
    write_mock.assert_not_awaited()
