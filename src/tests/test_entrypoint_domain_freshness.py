"""Integration test: chiron_entrypoint's per-Domain freshness pass (AC2, AC3).

Mocks at the underlying fetch boundary (``load_ohlcv``/``get_earnings_calendar``/
``get_earnings``/``get_news``, exactly what ``chiron_worker.recompute``'s
functions call internally) rather than the recompute functions themselves, so
each Domain's own internal ``raw_version`` compare is what's under test.
"""

import pandas as pd
import pytest

from chiron_entrypoint.entrypoint import _refresh_domains
from chiron_worker import recompute

STOCK = "PETR4.SA"


def _ohlcv_df(close: float) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Date": [pd.Timestamp("2026-08-01")],
            "Open": [10.0],
            "High": [11.0],
            "Low": [9.0],
            "Close": [close],
            "Volume": [1000],
        }
    )


_CALENDAR_CSV = "reportDate\n2099-01-01\n"
_EARNINGS_JSON = (
    '{"quarterlyEarnings": [{"fiscalDateEnding": "2026-06-30", "reportedDate": '
    '"2026-07-15", "reportedEPS": "1.0", "estimatedEPS": "0.9", "surprise": "0.1", '
    '"surprisePercentage": "11.1"}]}'
)


def _news_json(label: str) -> str:
    return (
        '{"feed": [{"time_published": "20260101T120000", "ticker_sentiment": '
        f'[{{"ticker": "{STOCK}", "ticker_sentiment_label": "{label}", '
        '"relevance_score": "0.9"}]}]}'
    )


def _patch_fetchers(monkeypatch, *, close: float, label: str) -> None:
    monkeypatch.setattr(recompute, "load_ohlcv", lambda ticker, curr_date: _ohlcv_df(close))
    monkeypatch.setattr(recompute, "get_earnings_calendar", lambda ticker: _CALENDAR_CSV)
    monkeypatch.setattr(recompute, "get_earnings", lambda ticker: _EARNINGS_JSON)
    monkeypatch.setattr(recompute, "get_news", lambda ticker, start, end: _news_json(label))


async def _updated_ats(cache_pool) -> dict[str, object]:
    async with cache_pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT domain, updated_at FROM domain_cache WHERE stock = $1", STOCK
        )
    return {row["domain"]: row["updated_at"] for row in rows}


@pytest.mark.integration
async def test_unchanged_fetch_data_skips_all_writes(monkeypatch, cache_pool):
    """Two freshness passes over identical fetch data: no Domain is rewritten (AC2)."""
    _patch_fetchers(monkeypatch, close=10.5, label="Neutral")

    await _refresh_domains(STOCK, STOCK)
    first_pass = await _updated_ats(cache_pool)
    assert set(first_pass) == {"price", "earnings", "news"}

    await _refresh_domains(STOCK, STOCK)
    second_pass = await _updated_ats(cache_pool)

    assert second_pass == first_pass


@pytest.mark.integration
async def test_one_changed_domain_refreshes_only_that_domain(monkeypatch, cache_pool):
    """Only the Domain whose fetched data changed gets a new ``updated_at`` (AC3)."""
    _patch_fetchers(monkeypatch, close=10.5, label="Neutral")
    await _refresh_domains(STOCK, STOCK)
    before = await _updated_ats(cache_pool)

    # Only Price's underlying fetch data changes this round.
    _patch_fetchers(monkeypatch, close=99.9, label="Neutral")
    await _refresh_domains(STOCK, STOCK)
    after = await _updated_ats(cache_pool)

    assert after["price"] != before["price"]
    assert after["earnings"] == before["earnings"]
    assert after["news"] == before["news"]
