"""Strategy-driven Domain weighting via a pure lookup function (AD-7, AD-9).

``chiron.config.json``'s ``strategy_weights`` section is the one source of
truth for per-Domain weights; this module never caches or mutates it — every
call re-reads the file so repeated calls over an unchanged config are
byte-identical (FR-10's weighting-specific guarantee), and no other module
may reformat the serialized weight context (AD-7).
"""

import json
from pathlib import Path

_DOMAIN_ORDER = ("price", "chart", "news", "graph", "earnings")


def config_path() -> Path:
    """Return the repo-root path of ``chiron.config.json``.

    ``chiron_cache`` owns this path-resolution helper (see module docstring
    in ``__init__.py``) — ``chiron_worker`` must import it from here rather
    than duplicating it, never the reverse.
    """
    return Path(__file__).resolve().parents[2] / "chiron.config.json"


def get_strategy_weights(strategy: str) -> dict[str, float]:
    """Return the per-Domain weight vector for ``strategy`` (``day``/``swing``).

    Reads and re-parses ``chiron.config.json`` on every call — no
    module-level caching — so two lookups seconds apart over an unchanged
    file return byte-identical output.
    """
    if strategy not in ("day", "swing"):
        raise ValueError(f"Unknown strategy: {strategy!r}")

    path = config_path()
    try:
        with path.open() as f:
            config = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"chiron.config.json not found at {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"chiron.config.json is not valid JSON: {exc}") from exc

    try:
        weights = config["strategy_weights"][strategy]
        return {domain: weights[domain] for domain in _DOMAIN_ORDER}
    except KeyError as exc:
        raise ValueError(
            f"chiron.config.json's strategy_weights.{strategy} is missing key {exc}"
        ) from exc


def format_strategy_weight_context(strategy: str) -> str:
    """Render ``strategy``'s weight vector as the single shared prompt-injection string.

    Both the Research Manager and Portfolio Manager inject this verbatim
    (AC3) — no other code path may reformat, truncate, or reorder it.
    """
    weights = get_strategy_weights(strategy)
    rendered = ", ".join(f"{domain}={value:.2f}" for domain, value in weights.items())
    return f"Strategy weights ({strategy}): {rendered}"


def get_tracked_tickers() -> list[str]:
    """Return ``chiron.config.json``'s ``tickers`` list, as written (AD-9).

    Reuses the same repo-root-relative path resolution as
    ``get_strategy_weights`` so behavior is identical regardless of the
    caller's invocation directory.
    """
    path = config_path()
    try:
        with path.open() as f:
            config = json.load(f)
    except FileNotFoundError:
        raise ValueError(f"chiron.config.json not found at {path}") from None
    except json.JSONDecodeError as exc:
        raise ValueError(f"chiron.config.json is not valid JSON: {exc}") from exc

    tickers = config.get("tickers")
    if not isinstance(tickers, list) or not tickers:
        raise ValueError("chiron.config.json's 'tickers' must be a non-empty list")
    return tickers
