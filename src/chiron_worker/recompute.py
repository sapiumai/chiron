"""Per-Domain recompute functions: fetch, compare ``raw_version``, write (AC2, AC3).

Each function fetches its Domain's Raw Atom(s), normalizes them into AD-4's
fixed payload shape, and only calls ``write_domain_cache`` inside
``domain_lock`` when the freshly computed ``raw_version`` differs from the
row already stored — an unchanged ``raw_version`` means no recompute cost was
wasted (there was none: the fetch already happened) but critically no write
happens, so ``updated_at`` is not bumped (AC2).

Zero existing ``async def``/``asyncio`` usage lives in ``src/chiron/`` (grep-
confirmed at story creation) — every existing sync fetcher call here goes
through ``asyncio.to_thread`` so the worker's event loop is never blocked.
"""

import asyncio
import csv
import io
import json
import logging
from datetime import date, datetime, timedelta

from chiron.dataflows.alpha_vantage_earnings import get_earnings, get_earnings_calendar
from chiron.dataflows.alpha_vantage_news import get_news
from chiron.dataflows.stockstats_utils import load_ohlcv
from chiron_cache import compute_raw_version, domain_lock, read_domain_cache, write_domain_cache

from .rate_limiter import VendorRateLimiter

logger = logging.getLogger(__name__)

_ALPHA_VANTAGE_VENDOR = "alpha_vantage"

# News lookback window: long enough to catch the last few trading days'
# coverage on a Domain job firing every few minutes (chiron.config.json's
# `domains.news.seconds`), short enough to keep each fetch small.
_NEWS_LOOKBACK_DAYS = 7


async def _write_if_changed(pool, domain: str, stock: str, payload, raw_version: str) -> None:
    """Write ``payload`` for ``(domain, stock)`` only if ``raw_version`` changed.

    Both the freshness read and the conditional write happen inside the same
    ``domain_lock`` transaction — never split into two transactions.
    """
    async with domain_lock(pool, domain, stock) as conn:
        row = await read_domain_cache(conn, domain, stock)
        if row is not None and row["raw_version"] == raw_version:
            return
        await write_domain_cache(conn, domain, stock, payload, raw_version)


def _normalize_ohlcv(df) -> list[dict]:
    """AD-4's Price payload: ``[{"date","open","high","low","close","volume"}, ...]``,
    ascending by date. Column order/semantics are verbatim from the source
    DataFrame; only the key casing is lowercased.
    """
    ordered = df.sort_values("Date")
    records = []
    for row in ordered.itertuples(index=False):
        records.append(
            {
                "date": row.Date.strftime("%Y-%m-%d")
                if hasattr(row.Date, "strftime")
                else str(row.Date),
                "open": float(row.Open),
                "high": float(row.High),
                "low": float(row.Low),
                "close": float(row.Close),
                "volume": float(row.Volume),
            }
        )
    return records


async def recompute_price(pool, ticker: str, stock: str) -> None:
    """Price Domain: wrap the sync ``load_ohlcv`` fetch in a thread, normalize, write."""
    today_str = date.today().isoformat()
    df = await asyncio.to_thread(load_ohlcv, ticker, today_str)
    ohlcv = _normalize_ohlcv(df)
    payload = {"ohlcv": ohlcv}
    raw_version = compute_raw_version(ohlcv)
    await _write_if_changed(pool, "price", stock, payload, raw_version)


def _parse_next_report_date(calendar_csv: str, today: date) -> str | None:
    """Earliest ``reportDate`` in ``calendar_csv`` on or after ``today``, or None."""
    reader = csv.DictReader(io.StringIO(calendar_csv))
    upcoming = []
    for row in reader:
        raw_date = row.get("reportDate")
        if not raw_date:
            continue
        try:
            parsed = datetime.strptime(raw_date, "%Y-%m-%d").date()
        except ValueError:
            continue
        if parsed >= today:
            upcoming.append(parsed)
    return min(upcoming).isoformat() if upcoming else None


def _parse_earnings_line_items(earnings_json: str) -> dict:
    """Most recent quarterly earnings entry, as AD-4's ``line_items`` dict.

    Alpha Vantage's ``EARNINGS`` response orders ``quarterlyEarnings``
    most-recent-first.
    """
    try:
        payload = json.loads(earnings_json)
    except (json.JSONDecodeError, TypeError):
        return {}
    quarterly = payload.get("quarterlyEarnings") if isinstance(payload, dict) else None
    if not quarterly:
        return {}
    latest = quarterly[0]
    return {
        "fiscal_date_ending": latest.get("fiscalDateEnding"),
        "reported_date": latest.get("reportedDate"),
        "reported_eps": latest.get("reportedEPS"),
        "estimated_eps": latest.get("estimatedEPS"),
        "surprise": latest.get("surprise"),
        "surprise_percentage": latest.get("surprisePercentage"),
    }


async def recompute_earnings(
    pool, ticker: str, stock: str, rate_limiter: VendorRateLimiter
) -> None:
    """Earnings Domain: fetch calendar + historical earnings, normalize, write.

    Two outbound Alpha Vantage calls per tick (calendar, then earnings
    history); each is gated on the shared vendor counter separately, since the
    cap tracks actual outbound calls, not ticks. Exhausting the cap between
    the two calls skips the tick entirely rather than writing a half-fetched
    payload.
    """
    if not rate_limiter.try_acquire(_ALPHA_VANTAGE_VENDOR):
        logger.info("earnings tick for %s skipped: alpha_vantage daily cap reached", stock)
        return
    calendar_csv = await asyncio.to_thread(get_earnings_calendar, ticker)

    if not rate_limiter.try_acquire(_ALPHA_VANTAGE_VENDOR):
        logger.info("earnings tick for %s skipped mid-tick: alpha_vantage daily cap reached", stock)
        return
    earnings_json = await asyncio.to_thread(get_earnings, ticker)

    payload = {
        "next_report_date": _parse_next_report_date(calendar_csv, date.today()),
        "line_items": _parse_earnings_line_items(earnings_json),
    }
    raw_version = compute_raw_version(payload)
    await _write_if_changed(pool, "earnings", stock, payload, raw_version)


def _tendency_from_label(label: str | None) -> str:
    """AD-4's News Impact Signal ``tendency``, from Alpha Vantage's own
    documented sentiment-label buckets (``Bullish``/``Somewhat-Bullish``/
    ``Neutral``/``Somewhat-Bearish``/``Bearish``) rather than re-deriving
    thresholds from the raw numeric score.
    """
    if not label:
        return "neutral"
    low = label.lower()
    if "bullish" in low:
        return "up"
    if "bearish" in low:
        return "down"
    return "neutral"


def _parse_time_published(raw: str | None) -> str | None:
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y%m%dT%H%M%S").isoformat()
    except ValueError:
        return raw


def _normalize_news(news_json: str, ticker: str) -> dict:
    """AD-4's News Impact Signal shape: ``{"signals": [{"entity","tendency",
    "confidence","as_of"}, ...]}``.

    One signal per feed article that mentions ``ticker`` in its
    ``ticker_sentiment`` array. ``tendency`` comes from Alpha Vantage's own
    ``ticker_sentiment_label`` bucket; ``confidence`` is that entry's
    ``relevance_score`` (how relevant the article is to this specific
    ticker) rather than the sentiment score itself.
    """
    try:
        payload = json.loads(news_json)
    except (json.JSONDecodeError, TypeError):
        return {"signals": []}
    feed = payload.get("feed") if isinstance(payload, dict) else None
    if not feed:
        return {"signals": []}

    signals = []
    for item in feed:
        for ts in item.get("ticker_sentiment", []):
            if ts.get("ticker") != ticker:
                continue
            signals.append(
                {
                    "entity": ticker,
                    "tendency": _tendency_from_label(ts.get("ticker_sentiment_label")),
                    "confidence": float(ts.get("relevance_score") or 0.0),
                    "as_of": _parse_time_published(item.get("time_published")),
                }
            )
    return {"signals": signals}


async def recompute_news(pool, ticker: str, stock: str, rate_limiter: VendorRateLimiter) -> None:
    """News Domain: fetch recent sentiment, derive Impact Signals, write."""
    if not rate_limiter.try_acquire(_ALPHA_VANTAGE_VENDOR):
        logger.info("news tick for %s skipped: alpha_vantage daily cap reached", stock)
        return

    end = date.today()
    start = end - timedelta(days=_NEWS_LOOKBACK_DAYS)
    news_json = await asyncio.to_thread(get_news, ticker, start.isoformat(), end.isoformat())

    payload = _normalize_news(news_json, ticker)
    raw_version = compute_raw_version(payload)
    await _write_if_changed(pool, "news", stock, payload, raw_version)
