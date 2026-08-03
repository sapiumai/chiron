"""Load and validate ``chiron.config.json`` for the worker daemon (AD-9).

Fails fast at startup on any missing/malformed Domain trigger config, naming
the offending Domain/key — a silently-skipped or wrongly-defaulted Domain
would otherwise look like it registered correctly but never actually run.
"""

import json
from pathlib import Path
from typing import Any

DEFAULT_CONFIG_PATH = Path("chiron.config.json")

# Domains this story's worker registers jobs for. Chart/Graph (Epic 2/3) are
# not this story's concern (see Dev Notes: no Analyst Node/graph wiring here).
REQUIRED_DOMAINS = ("price", "earnings", "news")
VALID_TRIGGERS = ("interval", "cron", "date")

# Earnings and News share Alpha Vantage's single account-wide daily cap (AC5).
_SHARED_VENDOR_DOMAINS = ("earnings", "news")


class WorkerConfigError(ValueError):
    """Raised when ``chiron.config.json`` is missing or malformed for the worker."""


def load_worker_config(path: Path | str = DEFAULT_CONFIG_PATH) -> dict[str, Any]:
    """Load, validate, and return the parsed ``chiron.config.json``.

    Raises ``WorkerConfigError`` naming the offending domain/key on any
    missing file, invalid JSON, or malformed ``domains`` entry.
    """
    path = Path(path)
    if not path.exists():
        raise WorkerConfigError(f"chiron.config.json not found at {path}")

    try:
        raw = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise WorkerConfigError(f"chiron.config.json is not valid JSON: {exc}") from exc

    tickers = raw.get("tickers")
    if not isinstance(tickers, list) or not tickers:
        raise WorkerConfigError("chiron.config.json's 'tickers' must be a non-empty list")

    domains = raw.get("domains")
    if not isinstance(domains, dict):
        raise WorkerConfigError("chiron.config.json is missing a 'domains' object")

    for name in REQUIRED_DOMAINS:
        domain_cfg = domains.get(name)
        if not isinstance(domain_cfg, dict):
            raise WorkerConfigError(f"chiron.config.json is missing domains.{name}")

        trigger = domain_cfg.get("trigger")
        if trigger not in VALID_TRIGGERS:
            raise WorkerConfigError(
                f"domains.{name}.trigger must be one of {VALID_TRIGGERS}, got {trigger!r}"
            )

        if trigger == "interval":
            seconds = domain_cfg.get("seconds")
            if not isinstance(seconds, int | float) or isinstance(seconds, bool) or seconds <= 0:
                raise WorkerConfigError(
                    f"domains.{name}.seconds must be a positive number, got {seconds!r}"
                )

    for name in _SHARED_VENDOR_DOMAINS:
        rate_limit = domains[name].get("rate_limit_per_day")
        if not isinstance(rate_limit, int) or isinstance(rate_limit, bool) or rate_limit <= 0:
            raise WorkerConfigError(
                f"domains.{name}.rate_limit_per_day must be a positive integer, got {rate_limit!r}"
            )

    earnings_cap = domains["earnings"]["rate_limit_per_day"]
    news_cap = domains["news"]["rate_limit_per_day"]
    if earnings_cap != news_cap:
        raise WorkerConfigError(
            "domains.earnings.rate_limit_per_day "
            f"({earnings_cap}) and domains.news.rate_limit_per_day ({news_cap}) must be "
            "equal — Earnings and News share one Alpha Vantage account-wide cap"
        )

    return raw
