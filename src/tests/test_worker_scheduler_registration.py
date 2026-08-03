"""Unit tests for chiron_worker.scheduler job registration and isolation (AC1, AC4)."""

import pytest

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
