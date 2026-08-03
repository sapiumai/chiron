from .alpha_vantage_common import AlphaVantageRateLimitError, _make_api_request
from .stockstats_utils import yf_retry


def get_earnings_calendar(ticker: str, horizon: str = "3month") -> str:
    """Return Alpha Vantage's upcoming earnings-report calendar for ``ticker``.

    CSV text with columns ``symbol,name,reportDate,fiscalDateEnding,estimate,
    currency`` — one row per upcoming report within ``horizon``
    (``3month``/``6month``/``12month``, Alpha Vantage's own vocabulary).
    """
    params = {"symbol": ticker, "horizon": horizon}
    return yf_retry(
        lambda: _make_api_request("EARNINGS_CALENDAR", params),
        exceptions=AlphaVantageRateLimitError,
    )


def get_earnings(ticker: str) -> dict | str:
    """Return Alpha Vantage's historical annual/quarterly earnings for ``ticker``.

    JSON payload with ``annualEarnings``/``quarterlyEarnings`` arrays, each
    entry carrying ``fiscalDateEnding``, ``reportedDate``, ``reportedEPS``,
    ``estimatedEPS``, ``surprise``, ``surprisePercentage``.
    """
    params = {"symbol": ticker}
    return yf_retry(
        lambda: _make_api_request("EARNINGS", params),
        exceptions=AlphaVantageRateLimitError,
    )
