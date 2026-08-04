"""Pure Strategy -> per-Domain weight vector lookup (AC1, AC2, AC3, AC4, AC5, AC6)."""

import pytest

from chiron_cache import format_strategy_weight_context, get_strategy_weights

_EXPECTED = {
    "day": {"price": 0.15, "chart": 0.35, "news": 0.20, "graph": 0.15, "earnings": 0.15},
    "swing": {"price": 0.15, "chart": 0.10, "news": 0.15, "graph": 0.10, "earnings": 0.50},
}


@pytest.mark.unit
@pytest.mark.parametrize("strategy", ["day", "swing"])
def test_get_strategy_weights_returns_expected_vector(strategy):
    weights = get_strategy_weights(strategy)
    assert weights == _EXPECTED[strategy]
    assert list(weights.keys()) == ["price", "chart", "news", "graph", "earnings"]


@pytest.mark.unit
@pytest.mark.parametrize("strategy", ["day", "swing"])
def test_get_strategy_weights_is_byte_identical_across_calls(strategy):
    assert get_strategy_weights(strategy) == get_strategy_weights(strategy)


@pytest.mark.unit
def test_get_strategy_weights_rejects_unknown_strategy():
    with pytest.raises(ValueError, match="Unknown strategy"):
        get_strategy_weights("scalp")


@pytest.mark.unit
def test_day_vector_weights_chart_and_news_graph_above_earnings():
    day = get_strategy_weights("day")
    assert day["chart"] > day["earnings"]
    assert day["news"] + day["graph"] > day["earnings"]


@pytest.mark.unit
def test_swing_vector_weights_earnings_above_chart_news_graph():
    swing = get_strategy_weights("swing")
    assert swing["earnings"] > swing["chart"]
    assert swing["earnings"] > swing["news"]
    assert swing["earnings"] > swing["graph"]


@pytest.mark.unit
@pytest.mark.parametrize("strategy", ["day", "swing"])
def test_format_strategy_weight_context_contains_all_domains(strategy):
    text = format_strategy_weight_context(strategy)
    for domain, value in _EXPECTED[strategy].items():
        assert f"{domain}={value:.2f}" in text


@pytest.mark.unit
@pytest.mark.parametrize("strategy", ["day", "swing"])
def test_format_strategy_weight_context_is_identical_across_calls(strategy):
    assert format_strategy_weight_context(strategy) == format_strategy_weight_context(strategy)
