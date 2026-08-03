"""In-process shared rate-limit counter, keyed by data vendor (Task 3, AC5).

Earnings and News both call Alpha Vantage against one account-wide daily
cap — enforcing the cap per-Domain instead of per-vendor would let their
combined real calls double the account's actual limit. State resets at UTC
midnight; losing the counter on a daemon restart is an accepted MVP
tradeoff (AD-2: single long-running daemon, no persistence needed here).
"""

from datetime import UTC, datetime


class VendorRateLimiter:
    """Tracks today's call count per vendor against a fixed daily cap."""

    def __init__(self, limits: dict[str, int]) -> None:
        self._limits = dict(limits)
        self._counts: dict[str, int] = dict.fromkeys(limits, 0)
        self._reset_date = datetime.now(UTC).date()

    def _maybe_reset(self) -> None:
        today = datetime.now(UTC).date()
        if today != self._reset_date:
            self._reset_date = today
            self._counts = dict.fromkeys(self._limits, 0)

    def try_acquire(self, vendor: str) -> bool:
        """Record one call against ``vendor``'s cap and return whether it fit.

        Returns False (no call recorded) once today's cap is spent; the
        caller must treat that as a skipped, non-error tick.
        """
        self._maybe_reset()
        if self._counts[vendor] >= self._limits[vendor]:
            return False
        self._counts[vendor] += 1
        return True
