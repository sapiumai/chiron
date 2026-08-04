"""Unit tests for chiron_worker.scheduler job registration and isolation (AC1, AC4)."""

import asyncio
from datetime import datetime, timedelta

import pytest

from chiron_cache.locking import domain_lock, write_domain_cache
from chiron_worker import scheduler as scheduler_module

_CONFIG = {
    "tickers": ["AAPL"],
    "domains": {
        "price": {"trigger": "interval", "seconds": 900, "rate_limit_per_day": None},
        "earnings": {"trigger": "interval", "seconds": 86400, "rate_limit_per_day": 25},
        "news": {"trigger": "interval", "seconds": 300, "rate_limit_per_day": 25},
    },
}


@pytest.mark.unit
def test_scheduler_registers_one_job_per_domain_with_max_instances_and_coalesce():
    scheduler = scheduler_module.build_scheduler(_CONFIG, pool=None)

    jobs = {job.id: job for job in scheduler.get_jobs()}
    assert set(jobs) == {"price", "earnings", "news"}
    for job in jobs.values():
        assert job.max_instances == 1
        assert job.coalesce is True


@pytest.mark.unit
def test_job_intervals_match_config_seconds():
    scheduler = scheduler_module.build_scheduler(_CONFIG, pool=None)
    jobs = {job.id: job for job in scheduler.get_jobs()}

    assert jobs["price"].trigger.interval.total_seconds() == 900
    assert jobs["earnings"].trigger.interval.total_seconds() == 86400
    assert jobs["news"].trigger.interval.total_seconds() == 300


@pytest.mark.unit
def test_interval_jobs_fire_immediately_on_daemon_start():
    """A freshly (re)started daemon must not leave every Domain stale for up
    to a full interval (24h for Earnings) before its first recompute."""
    before = datetime.now()
    scheduler = scheduler_module.build_scheduler(_CONFIG, pool=None)
    after = datetime.now()
    jobs = {job.id: job for job in scheduler.get_jobs()}

    for job in jobs.values():
        next_run = job.next_run_time.replace(tzinfo=None)
        assert before <= next_run <= after + timedelta(seconds=1)


@pytest.mark.unit
async def test_domain_job_swallows_errors_instead_of_raising():
    async def failing(ticker, stock):
        raise RuntimeError("Alpha Vantage down")

    job = scheduler_module._make_domain_job("news", failing, [("AAPL", "AAPL")])

    await job()  # must not raise


@pytest.mark.unit
async def test_failing_news_job_does_not_affect_other_domain_jobs():
    """AC4: News stalling/erroring must not stop Price/Earnings from ticking."""
    calls = []

    async def price_ok(ticker, stock):
        calls.append(("price", ticker))

    async def earnings_ok(ticker, stock):
        calls.append(("earnings", ticker))

    async def news_fail(ticker, stock):
        raise RuntimeError("Alpha Vantage down")

    price_job = scheduler_module._make_domain_job("price", price_ok, [("AAPL", "AAPL")])
    earnings_job = scheduler_module._make_domain_job("earnings", earnings_ok, [("AAPL", "AAPL")])
    news_job = scheduler_module._make_domain_job("news", news_fail, [("AAPL", "AAPL")])

    await news_job()
    await price_job()
    await earnings_job()

    assert calls == [("price", "AAPL"), ("earnings", "AAPL")]


@pytest.mark.unit
async def test_domain_job_continues_to_next_ticker_after_one_fails():
    calls = []

    async def flaky(ticker, stock):
        if ticker == "BAD":
            raise RuntimeError("boom")
        calls.append(ticker)

    job = scheduler_module._make_domain_job("price", flaky, [("BAD", "BAD"), ("AAPL", "AAPL")])

    await job()

    assert calls == ["AAPL"]


@pytest.mark.unit
async def test_domain_job_processes_tickers_concurrently_not_sequentially():
    """AC1: N tickers must complete in ~1x one ticker's duration, not Nx it."""
    sleep_seconds = 0.05
    tickers = [("A", "A"), ("B", "B"), ("C", "C"), ("D", "D")]

    async def slow_recompute(ticker, stock):
        await asyncio.sleep(sleep_seconds)

    job = scheduler_module._make_domain_job("price", slow_recompute, tickers)

    start = asyncio.get_event_loop().time()
    await job()
    elapsed = asyncio.get_event_loop().time() - start

    # Sequential would take ~4x sleep_seconds; concurrent should stay well under
    # that. Threshold is deliberately loose (vs. ~1x) to absorb CI scheduling
    # jitter without masking a regression back to sequential execution.
    assert elapsed < sleep_seconds * 2.5


@pytest.mark.unit
async def test_domain_job_isolates_multiple_ticker_failures_under_concurrency():
    """AC3: several tickers failing concurrently must not affect the rest."""
    calls = []
    tickers = [("BAD1", "BAD1"), ("OK1", "OK1"), ("BAD2", "BAD2"), ("OK2", "OK2")]

    async def flaky(ticker, stock):
        if ticker.startswith("BAD"):
            raise RuntimeError("boom")
        calls.append(ticker)

    job = scheduler_module._make_domain_job("price", flaky, tickers)

    await job()

    assert sorted(calls) == ["OK1", "OK2"]


@pytest.mark.integration
async def test_parallelized_domain_job_does_not_deadlock_across_ticker_locks(cache_pool):
    """AC4: concurrent tickers' domain_lock acquisitions must stay correctly
    scoped to their own ``(domain, stock)`` key — exercised through the
    actual parallelized ``_make_domain_job`` path, not ``domain_lock`` alone.
    """

    async def fake_recompute(ticker, stock):
        async with domain_lock(cache_pool, "price", stock) as conn:
            await asyncio.sleep(0.02)  # simulate recompute work while holding the lock
            await write_domain_cache(conn, "price", stock, {"ticker": ticker}, "v1")

    tickers = [("AAPL", "AAPL"), ("MSFT", "MSFT")]
    job = scheduler_module._make_domain_job("price", fake_recompute, tickers)

    await asyncio.wait_for(job(), timeout=5)
