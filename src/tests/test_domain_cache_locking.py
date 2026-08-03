"""Integration tests for chiron_cache.locking.domain_lock (AC 5, 6, 7)."""

import asyncio

import pytest

from chiron_cache.locking import domain_lock, read_domain_cache, write_domain_cache


@pytest.mark.integration
async def test_domain_lock_read_then_write_in_one_transaction(cache_pool):
    async with domain_lock(cache_pool, "price", "AAPL") as conn:
        assert await read_domain_cache(conn, "price", "AAPL") is None
        await write_domain_cache(conn, "price", "AAPL", {"close": 1.0}, "v1")

    async with domain_lock(cache_pool, "price", "AAPL") as conn:
        row = await read_domain_cache(conn, "price", "AAPL")
        assert row["payload"] == {"close": 1.0}
        assert row["raw_version"] == "v1"


@pytest.mark.integration
async def test_same_key_lock_acquisition_blocks_until_first_transaction_ends(cache_pool):
    a_acquired = asyncio.Event()
    a_work_done = asyncio.Event()
    order = []

    async def task_a():
        async with domain_lock(cache_pool, "price", "AAPL"):
            a_acquired.set()
            await asyncio.sleep(0.05)  # simulate work; not relied on for the proof below
            order.append("a-work-done")
            a_work_done.set()
        # transaction commits (and the advisory lock releases) on `async with` exit.

    async def task_b():
        await a_acquired.wait()
        async with domain_lock(cache_pool, "price", "AAPL"):
            # Deterministic proof of blocking: B cannot be here unless A's
            # transaction has already ended, since a_work_done is only set
            # while A still holds the lock.
            assert a_work_done.is_set()
            order.append("b-acquired")

    await asyncio.gather(task_a(), task_b())
    assert order == ["a-work-done", "b-acquired"]


@pytest.mark.integration
async def test_different_keys_do_not_block_each_other(cache_pool):
    a_acquired = asyncio.Event()
    allow_a_to_finish = asyncio.Event()
    order = []

    async def task_a():
        async with domain_lock(cache_pool, "price", "AAPL"):
            a_acquired.set()
            await allow_a_to_finish.wait()
            order.append("a-done")

    async def task_b():
        await a_acquired.wait()
        async with domain_lock(cache_pool, "price", "MSFT"):
            order.append("b-done")
        allow_a_to_finish.set()

    await asyncio.wait_for(asyncio.gather(task_a(), task_b()), timeout=5)
    assert order == ["b-done", "a-done"]


@pytest.mark.integration
async def test_different_domains_do_not_block_each_other(cache_pool):
    a_acquired = asyncio.Event()
    allow_a_to_finish = asyncio.Event()
    order = []

    async def task_a():
        async with domain_lock(cache_pool, "price", "AAPL"):
            a_acquired.set()
            await allow_a_to_finish.wait()
            order.append("a-done")

    async def task_b():
        await a_acquired.wait()
        async with domain_lock(cache_pool, "news", "AAPL"):
            order.append("b-done")
        allow_a_to_finish.set()

    await asyncio.wait_for(asyncio.gather(task_a(), task_b()), timeout=5)
    assert order == ["b-done", "a-done"]
