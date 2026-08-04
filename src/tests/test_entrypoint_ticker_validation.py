"""Unit tests for chiron_entrypoint's request validation (AC1)."""

import pytest

from chiron_entrypoint.entrypoint import EntrypointRequestError, _validate_request


@pytest.mark.unit
def test_unknown_ticker_rejected_before_any_access():
    with pytest.raises(EntrypointRequestError, match="not tracked"):
        _validate_request("UNKNOWNX", "day")


@pytest.mark.unit
def test_invalid_strategy_rejected_before_any_access():
    with pytest.raises(EntrypointRequestError, match="Unknown strategy"):
        _validate_request("PETR4.SA", "scalp")


@pytest.mark.unit
def test_tracked_ticker_with_valid_strategy_passes():
    raw_ticker, normalized = _validate_request("PETR4.SA", "day")
    assert raw_ticker == "PETR4.SA"
    assert normalized == "PETR4.SA"


@pytest.mark.unit
def test_validation_normalizes_both_sides():
    raw_ticker, normalized = _validate_request("petr4.sa", "swing")
    assert raw_ticker == "PETR4.SA"
    assert normalized == "PETR4.SA"
