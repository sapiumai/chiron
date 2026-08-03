"""Unit test for AC 2 / Task 4: chiron_cache never re-derives `stock`.

Uses a stub connection (no live Postgres needed) to assert
`write_domain_cache` passes `stock` through unchanged to the query — i.e. it
is the caller's job to normalize via
`chiron.dataflows.symbol_utils.normalize_symbol`, and chiron_cache does not
silently correct a caller's mistake.
"""

import pytest

from chiron_cache.locking import write_domain_cache


class _RecordingConnection:
    def __init__(self):
        self.calls = []

    async def execute(self, query, *args):
        self.calls.append(args)


@pytest.mark.unit
async def test_write_domain_cache_stores_stock_verbatim():
    conn = _RecordingConnection()
    await write_domain_cache(conn, "price", "not-a-normalized-ticker", {}, "v1")

    (domain, stock, payload, raw_version) = conn.calls[0]
    assert domain == "price"
    assert stock == "not-a-normalized-ticker"
    assert payload == {}
    assert raw_version == "v1"
