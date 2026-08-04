"""Unit tests: a real caller-supplied ``strategy`` reaches the pipeline (AC6).

Story 1.5 left ``TradingAgentsGraph.propagate()``'s own signature
default-only; this story (Task 3) threads a real value through
``propagate()`` -> ``_run_graph()`` -> ``Propagator.create_initial_state()``.
These tests exercise that wiring directly rather than running a full graph
(see ``test_checkpoint_resume.py``'s ``object.__new__`` precedent for a bare
``TradingAgentsGraph`` instance), then confirm the same value reaches the
Research Manager prompt via Story 1.5's existing injection point.
"""

from unittest.mock import MagicMock

import pytest

from chiron.agents.managers.research_manager import create_research_manager
from chiron.graph.trading_graph import TradingAgentsGraph
from chiron_cache import format_strategy_weight_context


def _bare_graph() -> TradingAgentsGraph:
    """A minimally-wired TradingAgentsGraph instance, bypassing __init__."""
    g = object.__new__(TradingAgentsGraph)
    g.config = {"checkpoint_enabled": False}
    g.memory_log = MagicMock()
    g.memory_log.get_past_context.return_value = ""
    g.resolve_instrument_context = lambda ticker, asset_type="stock": ""
    g._checkpointer_ctx = None
    g._resolve_pending_entries = lambda company_name: None
    g.debug = False
    g.process_signal = lambda decision: decision
    g._log_state = lambda trade_date, final_state: None
    return g


@pytest.mark.unit
def test_propagate_forwards_real_strategy_into_initial_state():
    g = _bare_graph()

    captured = {}

    def _fake_create_initial_state(company_name, trade_date, **kwargs):
        captured.update(kwargs)
        return {"strategy": kwargs.get("strategy", "day")}

    propagator = MagicMock()
    propagator.create_initial_state.side_effect = _fake_create_initial_state
    propagator.get_graph_args.return_value = {}
    g.propagator = propagator

    g.graph = MagicMock()
    g.graph.invoke.return_value = {"final_trade_decision": "BUY"}

    g.propagate("PETR4.SA", "2026-08-04", strategy="swing")

    assert captured["strategy"] == "swing"


@pytest.mark.unit
def test_propagate_default_strategy_is_day_for_existing_callers():
    g = _bare_graph()

    captured = {}

    def _fake_create_initial_state(company_name, trade_date, **kwargs):
        captured.update(kwargs)
        return {"strategy": kwargs.get("strategy", "day")}

    propagator = MagicMock()
    propagator.create_initial_state.side_effect = _fake_create_initial_state
    propagator.get_graph_args.return_value = {}
    g.propagator = propagator

    g.graph = MagicMock()
    g.graph.invoke.return_value = {"final_trade_decision": "HOLD"}

    g.propagate("PETR4.SA", "2026-08-04")

    assert captured["strategy"] == "day"


@pytest.mark.unit
def test_forwarded_strategy_reaches_research_manager_prompt():
    """The value propagate() threads into state["strategy"] drives the same
    prompt injection Story 1.5 wired into the Research Manager.
    """
    from chiron.agents.schemas import PortfolioRating, ResearchPlan

    captured = {}

    def _capturing_llm(result):
        structured = MagicMock()
        structured.invoke.side_effect = lambda prompt: (
            captured.__setitem__("prompt", prompt) or (result)
        )
        llm = MagicMock()
        llm.with_structured_output.return_value = structured
        return llm

    def _prompt_text(prompt) -> str:
        if isinstance(prompt, str):
            return prompt
        parts = [
            m.get("content", "") if isinstance(m, dict) else getattr(m, "content", "")
            for m in prompt
        ]
        return "\n".join(str(p) for p in parts)

    llm = _capturing_llm(
        ResearchPlan(recommendation=PortfolioRating.BUY, rationale="x", strategic_actions="y")
    )
    create_research_manager(llm)(
        {
            "company_of_interest": "PETR4.SA",
            "strategy": "swing",  # the value propagate() would have forwarded
            "investment_debate_state": {
                "history": "h",
                "bull_history": "b",
                "bear_history": "r",
                "current_response": "",
                "judge_decision": "",
                "count": 1,
            },
        }
    )

    assert format_strategy_weight_context("swing") in _prompt_text(captured["prompt"])
