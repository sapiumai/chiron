"""Unit tests: chiron_entrypoint's output-file stage (AC4, AC5).

``TradingAgentsGraph.propagate``/``save_reports`` are mocked — this story's
own logic (composing the freshness pass with the pipeline call and the
report writer) is what's under test, not the LLM pipeline itself.
"""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

import chiron_entrypoint.entrypoint as entrypoint_module


@pytest.mark.unit
async def test_run_analysis_returns_existing_report_path(tmp_path, monkeypatch):
    monkeypatch.setattr(entrypoint_module, "_refresh_domains", AsyncMock())

    output_path = tmp_path / "reports" / "PETR4.SA_20260804_000000" / "complete_report.md"
    output_path.parent.mkdir(parents=True)
    output_path.write_text("# report")

    fake_final_state = {"final_trade_decision": "BUY"}
    fake_ta = MagicMock()
    fake_ta.propagate.return_value = (fake_final_state, "BUY")
    fake_ta.save_reports.return_value = output_path
    monkeypatch.setattr(entrypoint_module, "TradingAgentsGraph", MagicMock(return_value=fake_ta))

    result = await entrypoint_module.run_analysis("PETR4.SA", "day")

    assert result == output_path
    assert result.exists()
    fake_ta.save_reports.assert_called_once_with(fake_final_state, "PETR4.SA")


@pytest.mark.unit
async def test_run_analysis_passes_requested_strategy_to_propagate(tmp_path, monkeypatch):
    monkeypatch.setattr(entrypoint_module, "_refresh_domains", AsyncMock())

    output_path = tmp_path / "complete_report.md"
    output_path.write_text("# report")
    fake_ta = MagicMock()
    fake_ta.propagate.return_value = ({"final_trade_decision": "HOLD"}, "HOLD")
    fake_ta.save_reports.return_value = output_path
    monkeypatch.setattr(entrypoint_module, "TradingAgentsGraph", MagicMock(return_value=fake_ta))

    await entrypoint_module.run_analysis("PETR4.SA", "swing")

    _, kwargs = fake_ta.propagate.call_args
    assert kwargs["strategy"] == "swing"


@pytest.mark.unit
async def test_run_analysis_rejects_invalid_request_before_pipeline_or_refresh(monkeypatch):
    refresh_mock = AsyncMock()
    monkeypatch.setattr(entrypoint_module, "_refresh_domains", refresh_mock)
    graph_cls = MagicMock()
    monkeypatch.setattr(entrypoint_module, "TradingAgentsGraph", graph_cls)

    with pytest.raises(entrypoint_module.EntrypointRequestError):
        await entrypoint_module.run_analysis("NOT-TRACKED", "day")

    refresh_mock.assert_not_called()
    graph_cls.assert_not_called()


@pytest.mark.unit
def test_entrypoint_never_writes_the_recommendation_to_domain_cache():
    """AC5: no code path in this module writes to ``domain_cache`` — a
    negative, structural check (this module never even imports
    ``write_domain_cache``; only ``chiron_worker.recompute``'s Domain
    refresh functions do, and those write Raw-Atom Domain payloads, never
    the recommendation itself).
    """
    source = Path(entrypoint_module.__file__).read_text()
    assert "write_domain_cache" not in source
