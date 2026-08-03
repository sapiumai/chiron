"""Unit tests for chiron_worker.recompute's Earnings Domain path (AC2, AC3, AC5)."""

import json
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock

import pytest

from chiron_worker import recompute
from chiron_worker.rate_limiter import VendorRateLimiter

_CALENDAR_CSV = (
    "symbol,name,reportDate,fiscalDateEnding,estimate,currency\n"
    "AAPL,Apple Inc,2026-10-30,2026-09-30,1.5,USD\n"
)

_EARNINGS_JSON = json.dumps(
    {
        "symbol": "AAPL",
        "quarterlyEarnings": [
            {
                "fiscalDateEnding": "2026-06-30",
                "reportedDate": "2026-07-25",
                "reportedEPS": "1.4",
                "estimatedEPS": "1.35",
                "surprise": "0.05",
                "surprisePercentage": "3.7",
            }
        ],
    }
)


@asynccontextmanager
async def _fake_domain_lock(pool, domain, stock):
    yield "conn"


def test_parse_next_report_date_picks_earliest_upcoming():
    from datetime import date

    result = recompute._parse_next_report_date(_CALENDAR_CSV, date(2026, 8, 3))
    assert result == "2026-10-30"


def test_parse_next_report_date_ignores_past_reports():
    from datetime import date

    result = recompute._parse_next_report_date(_CALENDAR_CSV, date(2026, 11, 1))
    assert result is None


def test_parse_earnings_line_items_uses_most_recent_quarter():
    line_items = recompute._parse_earnings_line_items(_EARNINGS_JSON)
    assert line_items["fiscal_date_ending"] == "2026-06-30"
    assert line_items["reported_eps"] == "1.4"


@pytest.mark.unit
async def test_earnings_recompute_writes_when_changed(monkeypatch):
    write_mock = AsyncMock()
    monkeypatch.setattr(recompute, "get_earnings_calendar", lambda ticker: _CALENDAR_CSV)
    monkeypatch.setattr(recompute, "get_earnings", lambda ticker: _EARNINGS_JSON)
    monkeypatch.setattr(recompute, "read_domain_cache", AsyncMock(return_value=None))
    monkeypatch.setattr(recompute, "write_domain_cache", write_mock)
    monkeypatch.setattr(recompute, "domain_lock", _fake_domain_lock)

    limiter = VendorRateLimiter({"alpha_vantage": 10})
    await recompute.recompute_earnings(pool=None, ticker="AAPL", stock="AAPL", rate_limiter=limiter)

    write_mock.assert_awaited_once()


@pytest.mark.unit
async def test_earnings_recompute_skips_tick_when_cap_exhausted(monkeypatch):
    fetch_mock = AsyncMock()
    monkeypatch.setattr(recompute, "get_earnings_calendar", lambda ticker: fetch_mock())
    monkeypatch.setattr(recompute, "get_earnings", lambda ticker: fetch_mock())
    write_mock = AsyncMock()
    monkeypatch.setattr(recompute, "write_domain_cache", write_mock)
    monkeypatch.setattr(recompute, "domain_lock", _fake_domain_lock)

    limiter = VendorRateLimiter({"alpha_vantage": 0})
    await recompute.recompute_earnings(pool=None, ticker="AAPL", stock="AAPL", rate_limiter=limiter)

    fetch_mock.assert_not_called()
    write_mock.assert_not_awaited()
