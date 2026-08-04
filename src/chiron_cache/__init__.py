"""Generic Postgres cache layer: content-hash versioning + advisory locking.

Pure Postgres + config — must never import from ``chiron_worker`` or
``chiron_entrypoint`` (see architecture spine, "Design Paradigm").
"""

from chiron_cache.db import create_pool
from chiron_cache.locking import domain_lock, read_domain_cache, write_domain_cache
from chiron_cache.schema import ensure_schema
from chiron_cache.strategy_weights import (
    format_strategy_weight_context,
    get_strategy_weights,
)
from chiron_cache.versioning import compute_raw_version

__all__ = [
    "create_pool",
    "domain_lock",
    "read_domain_cache",
    "write_domain_cache",
    "ensure_schema",
    "compute_raw_version",
    "get_strategy_weights",
    "format_strategy_weight_context",
]
