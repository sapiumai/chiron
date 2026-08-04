"""Cache-hit skip retrofit for Market, Fundamentals, News analysts (Story 1.4).

Covers the cache-hit short-circuit path (no LLM call) and the cache-miss
regression path (existing LLM/tool-call behavior unchanged) for each of the
three cache-mapped analysts, plus a drift-guard confirming the Sentiment
Analyst was never touched.
"""

import inspect
from unittest.mock import MagicMock, patch

import pytest

import chiron.agents.analysts.sentiment_analyst as sentiment_analyst_module
from chiron.agents.analysts.fundamentals_analyst import create_fundamentals_analyst
from chiron.agents.analysts.market_analyst import create_market_analyst
from chiron.agents.analysts.news_analyst import create_news_analyst


def _base_state(**overrides):
    state = {
        "trade_date": "2026-08-03",
        "company_of_interest": "AAPL",
        "messages": [],
    }
    state.update(overrides)
    return state


def _mock_llm_with_final_response(content: str):
    llm = MagicMock()
    bound = MagicMock()
    result = MagicMock(content=content, tool_calls=[])
    bound.return_value = result
    bound.invoke.return_value = result
    llm.bind_tools.return_value = bound
    return llm


MARKET_PAYLOAD = {
    "ohlcv": [
        {
            "date": "2026-08-01",
            "open": 100,
            "high": 105,
            "low": 99,
            "close": 104,
            "volume": 1000000,
        },
        {
            "date": "2026-08-02",
            "open": 104,
            "high": 106,
            "low": 103,
            "close": 105,
            "volume": 1200000,
        },
    ]
}

EARNINGS_PAYLOAD = {
    "next_report_date": "2026-10-15",
    "line_items": {"revenue": 1000000, "net_income": 200000},
}

NEWS_PAYLOAD = {
    "signals": [
        {"entity": "AAPL", "tendency": "up", "confidence": 0.8, "as_of": "2026-08-02"},
    ]
}


@pytest.mark.unit
class TestMarketAnalystCacheHitSkip:
    def test_cache_hit_skips_llm(self):
        llm = _mock_llm_with_final_response("unused")
        with patch(
            "chiron.agents.analysts.market_analyst.get_cached_payload",
            return_value=MARKET_PAYLOAD,
        ):
            node = create_market_analyst(llm)
            result = node(_base_state())

        assert result["market_report"]
        assert "2026-08-01" in result["market_report"]
        assert "2026-08-02" in result["market_report"]
        assert "104" in result["market_report"]
        assert "105" in result["market_report"]
        assert result["messages"][0].tool_calls == []
        llm.bind_tools.assert_not_called()

    def test_cache_miss_falls_back_to_llm(self):
        llm = _mock_llm_with_final_response("Market report from LLM")
        with patch(
            "chiron.agents.analysts.market_analyst.get_cached_payload",
            return_value=None,
        ):
            node = create_market_analyst(llm)
            result = node(_base_state())

        assert result["market_report"] == "Market report from LLM"
        llm.bind_tools.assert_called_once()

    def test_empty_cache_payload_falls_back_to_llm(self):
        llm = _mock_llm_with_final_response("Market report from LLM")
        with patch(
            "chiron.agents.analysts.market_analyst.get_cached_payload",
            return_value={"ohlcv": []},
        ):
            node = create_market_analyst(llm)
            result = node(_base_state())

        assert result["market_report"] == "Market report from LLM"
        llm.bind_tools.assert_called_once()


@pytest.mark.unit
class TestFundamentalsAnalystCacheHitSkip:
    def test_cache_hit_skips_llm(self):
        llm = _mock_llm_with_final_response("unused")
        with patch(
            "chiron.agents.analysts.fundamentals_analyst.get_cached_payload",
            return_value=EARNINGS_PAYLOAD,
        ):
            node = create_fundamentals_analyst(llm)
            result = node(_base_state())

        assert result["fundamentals_report"]
        assert "2026-10-15" in result["fundamentals_report"]
        assert result["messages"][0].tool_calls == []
        llm.bind_tools.assert_not_called()

    def test_cache_miss_falls_back_to_llm(self):
        llm = _mock_llm_with_final_response("Fundamentals report from LLM")
        with patch(
            "chiron.agents.analysts.fundamentals_analyst.get_cached_payload",
            return_value=None,
        ):
            node = create_fundamentals_analyst(llm)
            result = node(_base_state())

        assert result["fundamentals_report"] == "Fundamentals report from LLM"
        llm.bind_tools.assert_called_once()

    def test_empty_cache_payload_falls_back_to_llm(self):
        llm = _mock_llm_with_final_response("Fundamentals report from LLM")
        with patch(
            "chiron.agents.analysts.fundamentals_analyst.get_cached_payload",
            return_value={"next_report_date": "2026-10-15", "line_items": {}},
        ):
            node = create_fundamentals_analyst(llm)
            result = node(_base_state())

        assert result["fundamentals_report"] == "Fundamentals report from LLM"
        llm.bind_tools.assert_called_once()


@pytest.mark.unit
class TestNewsAnalystCacheHitSkip:
    def test_cache_hit_skips_llm(self):
        llm = _mock_llm_with_final_response("unused")
        with patch(
            "chiron.agents.analysts.news_analyst.get_cached_payload",
            return_value=NEWS_PAYLOAD,
        ):
            node = create_news_analyst(llm)
            result = node(_base_state())

        assert result["news_report"]
        assert "AAPL" in result["news_report"]
        assert result["messages"][0].tool_calls == []
        llm.bind_tools.assert_not_called()

    def test_cache_miss_falls_back_to_llm(self):
        llm = _mock_llm_with_final_response("News report from LLM")
        with patch(
            "chiron.agents.analysts.news_analyst.get_cached_payload",
            return_value=None,
        ):
            node = create_news_analyst(llm)
            result = node(_base_state())

        assert result["news_report"] == "News report from LLM"
        llm.bind_tools.assert_called_once()

    def test_empty_cache_payload_falls_back_to_llm(self):
        llm = _mock_llm_with_final_response("News report from LLM")
        with patch(
            "chiron.agents.analysts.news_analyst.get_cached_payload",
            return_value={"signals": []},
        ):
            node = create_news_analyst(llm)
            result = node(_base_state())

        assert result["news_report"] == "News report from LLM"
        llm.bind_tools.assert_called_once()


@pytest.mark.unit
def test_sentiment_analyst_has_no_cache_references():
    src = inspect.getsource(sentiment_analyst_module)
    assert "chiron_cache" not in src
    assert "get_cached_payload" not in src


@pytest.mark.unit
def test_get_cached_payload_treats_lookup_failure_as_miss():
    from chiron.agents.utils.cache_lookup import get_cached_payload

    with patch(
        "chiron.agents.utils.cache_lookup.create_pool",
        side_effect=RuntimeError("TRADINGAGENTS_POSTGRES_DSN is not set"),
    ):
        assert get_cached_payload("price", "AAPL") is None
