"""On-demand analysis request entry point (FR-11).

A thin composition layer over ``chiron`` (pipeline), ``chiron_cache``
(freshness/weighting), and ``chiron_worker`` (per-Domain recompute) — never
the reverse (see architecture spine, "Design Paradigm").
"""

from chiron_entrypoint.entrypoint import EntrypointRequestError, run_analysis

__all__ = ["EntrypointRequestError", "run_analysis"]
