"""On-demand analysis entry point: validate a request, refresh stale Domains, run the pipeline.

Composition-only layer (AD-1): reuses Story 1.3's per-Domain recompute
functions, Story 1.5's strategy weighting (transitively, via
``propagate()``'s ``strategy`` threading), and the existing report-tree
writer — no new Domain/Analyst Node logic lives here.
"""

import asyncio
import logging
from datetime import datetime
from pathlib import Path

from chiron.dataflows.symbol_utils import normalize_symbol
from chiron.graph.trading_graph import TradingAgentsGraph
from chiron_cache import config_path, create_pool, ensure_schema, get_tracked_tickers
from chiron_worker.config import load_worker_config
from chiron_worker.rate_limiter import VendorRateLimiter
from chiron_worker.recompute import recompute_earnings, recompute_news, recompute_price

logger = logging.getLogger(__name__)

VALID_STRATEGIES = ("day", "swing")

# Reuses chiron_cache's own repo-root-relative path resolution — never
# CWD-relative like chiron_worker.config.DEFAULT_CONFIG_PATH.
_CONFIG_PATH = config_path()


class EntrypointRequestError(ValueError):
    """Raised when a requested ``(stock, strategy)`` fails validation (AC1)."""


def _validate_request(stock: str, strategy: str) -> tuple[str, str]:
    """Return ``(raw_ticker, normalized_stock)`` for a valid request.

    Raises ``EntrypointRequestError`` before any Postgres/LLM access for an
    unknown ticker or invalid strategy (AC1).
    """
    if strategy not in VALID_STRATEGIES:
        raise EntrypointRequestError(
            f"Unknown strategy {strategy!r}; must be one of {VALID_STRATEGIES}"
        )

    normalized = normalize_symbol(stock)
    for raw in get_tracked_tickers():
        if normalize_symbol(raw) == normalized:
            return raw, normalized

    raise EntrypointRequestError(
        f"Stock {stock!r} is not tracked in chiron.config.json's 'tickers' list"
    )


async def _refresh_domains(raw_ticker: str, stock: str) -> None:
    """Refresh Price/Earnings/News for ``stock`` (AC2, AC3).

    Each recompute function opens its own ``domain_lock`` internally and
    only writes when its freshly computed ``raw_version`` differs from what
    is already cached — no freshness logic is duplicated here.
    """
    config = load_worker_config(_CONFIG_PATH)
    rate_limiter = VendorRateLimiter(
        {"alpha_vantage": config["domains"]["earnings"]["rate_limit_per_day"]}
    )

    pool = await create_pool()
    try:
        async with pool.acquire() as conn:
            await ensure_schema(conn)
        await recompute_price(pool, raw_ticker, stock)
        await recompute_earnings(pool, raw_ticker, stock, rate_limiter)
        await recompute_news(pool, raw_ticker, stock, rate_limiter)
    finally:
        await pool.close()


async def run_analysis(stock: str, strategy: str) -> Path:
    """Validate, refresh Domains, run the pipeline, and write the report (AC1-6).

    Returns the path to the written ``complete_report.md``.
    """
    raw_ticker, normalized_stock = _validate_request(stock, strategy)

    await _refresh_domains(raw_ticker, normalized_stock)

    trade_date = datetime.now().strftime("%Y-%m-%d")
    ta = TradingAgentsGraph()
    final_state, _ = await asyncio.to_thread(
        ta.propagate, normalized_stock, trade_date, strategy=strategy
    )
    output_path = ta.save_reports(final_state, normalized_stock)

    logger.info(
        "Analysis complete: ticker=%s strategy=%s output=%s decision=%s",
        normalized_stock,
        strategy,
        output_path,
        final_state.get("final_trade_decision"),
    )
    return output_path
