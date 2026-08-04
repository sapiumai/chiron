"""Unit tests for chiron_worker.rate_limiter's shared Alpha Vantage counter (AC5)."""

import asyncio
from datetime import UTC, datetime

import pytest

from chiron_worker import rate_limiter as rate_limiter_module
from chiron_worker.rate_limiter import VendorRateLimiter


@pytest.mark.unit
def test_combined_earnings_and_news_calls_capped_at_shared_limit():
    """Earnings and News share one counter — combined calls stop at the configured cap,
    never double-counted independently per Domain.
    """
    limiter = VendorRateLimiter({"alpha_vantage": 3})

    results = []
    for i in range(5):
        vendor_call_is_earnings = i % 2 == 0
        results.append((vendor_call_is_earnings, limiter.try_acquire("alpha_vantage")))

    acquired = [ok for _, ok in results]
    assert acquired == [True, True, True, False, False]


@pytest.mark.unit
def test_try_acquire_is_a_noop_error_when_exhausted():
    limiter = VendorRateLimiter({"alpha_vantage": 1})
    assert limiter.try_acquire("alpha_vantage") is True
    assert limiter.try_acquire("alpha_vantage") is False
    # Exhaustion doesn't raise or corrupt state — a repeated check still returns False.
    assert limiter.try_acquire("alpha_vantage") is False


class _FakeDatetime:
    current: datetime

    @classmethod
    def now(cls, tz=None):
        return cls.current


@pytest.mark.unit
def test_counter_resets_after_utc_midnight(monkeypatch):
    _FakeDatetime.current = datetime(2026, 8, 3, 23, 0, tzinfo=UTC)
    monkeypatch.setattr(rate_limiter_module, "datetime", _FakeDatetime)

    limiter = VendorRateLimiter({"alpha_vantage": 1})
    assert limiter.try_acquire("alpha_vantage") is True
    assert limiter.try_acquire("alpha_vantage") is False

    _FakeDatetime.current = datetime(2026, 8, 4, 0, 5, tzinfo=UTC)
    assert limiter.try_acquire("alpha_vantage") is True


@pytest.mark.unit
async def test_try_acquire_is_safe_under_concurrent_callers():
    """AC2 regression: `try_acquire` has no `await` inside it, so concurrent
    `asyncio.gather`-scheduled callers (from this story's parallelized
    per-ticker fan-out) can never collectively exceed the shared cap — each
    call runs to completion atomically on the single event loop thread.
    """
    limiter = VendorRateLimiter({"alpha_vantage": 3})

    async def call() -> bool:
        await asyncio.sleep(0)  # yield first so all 10 calls interleave, not run back-to-back
        return limiter.try_acquire("alpha_vantage")

    results = await asyncio.gather(*(call() for _ in range(10)))

    assert sum(results) == 3
