"""Register one AsyncIOScheduler job per Domain, from ``chiron.config.json`` (AD-3).

Adding a Domain is a config-only change: this module reads ``domains`` and
registers a job per key, mapping its ``trigger`` straight onto APScheduler's
matching trigger kwargs — no per-Domain branching beyond what a Domain's own
recompute function needs.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from asyncpg import Pool

from chiron.dataflows.symbol_utils import normalize_symbol

from .rate_limiter import VendorRateLimiter
from .recompute import recompute_earnings, recompute_news, recompute_price

logger = logging.getLogger(__name__)


def _trigger_kwargs(domain_cfg: dict) -> dict:
    trigger = domain_cfg["trigger"]
    if trigger == "interval":
        # next_run_time=now overrides IntervalTrigger's own default first-fire
        # time, which is otherwise one full interval away — without this, a
        # freshly (re)started daemon leaves every Domain stale for up to its
        # own interval (24h for Earnings) before ever recomputing anything.
        return {
            "trigger": "interval",
            "seconds": domain_cfg["seconds"],
            "next_run_time": datetime.now(),
        }
    # cron/date aren't used by this story's own config (price/earnings/news are
    # all interval-triggered here), but any future Domain using them needs no
    # code change: APScheduler's own kwarg names apply unchanged (AD-3). Their
    # own explicit schedule (e.g. "daily at 9am") should not be forced to also
    # fire immediately on daemon start, unlike a plain interval.
    extra = {k: v for k, v in domain_cfg.items() if k not in ("trigger", "rate_limit_per_day")}
    return {"trigger": trigger, **extra}


def _make_domain_job(
    domain: str,
    recompute: Callable[[str, str], Awaitable[None]],
    tickers: list[tuple[str, str]],
    pool_semaphore: asyncio.Semaphore | None = None,
) -> Callable[[], Awaitable[None]]:
    """Build a job body that recomputes ``domain`` for every configured ticker
    concurrently, so a job with N tickers takes roughly as long as the
    slowest single ticker's recompute rather than N times that (AC1).

    Each ticker's recompute is individually try/except-guarded *inside its
    own gathered coroutine* so one ticker's failure doesn't cancel or stop
    the others' concurrent execution, and the whole job never raises into
    APScheduler — a failing/slow Domain must never stall the others (AC3).

    ``pool_semaphore``, when given, bounds how many tickers' recomputes may
    hold a pool connection (via ``domain_lock``) at once — shared across all
    three Domain jobs so their combined fan-out can never exceed the pool's
    capacity, regardless of how many tickers ``chiron.config.json`` lists.
    """

    async def _run_one(ticker: str, stock: str) -> None:
        try:
            if pool_semaphore is None:
                await recompute(ticker, stock)
            else:
                async with pool_semaphore:
                    await recompute(ticker, stock)
        except Exception:
            logger.exception("%s Domain job failed for %s", domain, stock)

    async def job() -> None:
        # A daemon shutdown/cancellation while this gather is in flight cancels
        # every in-progress ticker's recompute together, not just one — unlike
        # the old sequential loop. This is safe: domain_lock's transaction is
        # rolled back on cancellation just as on any other exception, so no
        # partial write can land.
        await asyncio.gather(*(_run_one(ticker, stock) for ticker, stock in tickers))

    return job


def build_scheduler(config: dict, pool: Pool) -> AsyncIOScheduler:
    """Build (but do not start) an AsyncIOScheduler with one job per Domain."""
    domains = config["domains"]
    tickers = [(raw, normalize_symbol(raw)) for raw in config["tickers"]]

    # One counter shared by Earnings and News — both call Alpha Vantage against
    # a single account-wide cap (AC5). load_worker_config already asserted the
    # two configured caps are equal.
    rate_limiter = VendorRateLimiter({"alpha_vantage": domains["earnings"]["rate_limit_per_day"]})

    # Shared across all three Domain jobs so their concurrent per-ticker fan-out
    # (AC1) can never collectively hold more connections than the pool has,
    # no matter how many tickers chiron.config.json lists. Tests may pass
    # pool=None since they never call into a job body that needs a connection.
    pool_semaphore = asyncio.Semaphore(max(1, pool.get_max_size() // 3)) if pool else None

    scheduler = AsyncIOScheduler()

    async def _price(ticker: str, stock: str) -> None:
        await recompute_price(pool, ticker, stock)

    async def _earnings(ticker: str, stock: str) -> None:
        await recompute_earnings(pool, ticker, stock, rate_limiter)

    async def _news(ticker: str, stock: str) -> None:
        await recompute_news(pool, ticker, stock, rate_limiter)

    scheduler.add_job(
        _make_domain_job("price", _price, tickers, pool_semaphore),
        id="price",
        max_instances=1,
        coalesce=True,
        **_trigger_kwargs(domains["price"]),
    )
    scheduler.add_job(
        _make_domain_job("earnings", _earnings, tickers, pool_semaphore),
        id="earnings",
        max_instances=1,
        coalesce=True,
        **_trigger_kwargs(domains["earnings"]),
    )
    scheduler.add_job(
        _make_domain_job("news", _news, tickers, pool_semaphore),
        id="news",
        max_instances=1,
        coalesce=True,
        **_trigger_kwargs(domains["news"]),
    )

    return scheduler
