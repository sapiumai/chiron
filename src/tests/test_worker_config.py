"""Unit tests for chiron_worker.config's fail-fast validation."""

import json

import pytest

from chiron_worker.config import WorkerConfigError, load_worker_config

_VALID = {
    "tickers": ["PETR4.SA"],
    "strategy_weights": {},
    "domains": {
        "price": {"trigger": "interval", "seconds": 900, "rate_limit_per_day": None},
        "earnings": {"trigger": "interval", "seconds": 86400, "rate_limit_per_day": 25},
        "news": {"trigger": "interval", "seconds": 300, "rate_limit_per_day": 25},
    },
}


def _write_config(tmp_path, data):
    path = tmp_path / "chiron.config.json"
    path.write_text(json.dumps(data))
    return path


@pytest.mark.unit
def test_valid_config_loads(tmp_path):
    path = _write_config(tmp_path, _VALID)
    assert load_worker_config(path) == _VALID


@pytest.mark.unit
def test_missing_file_raises_clear_error(tmp_path):
    with pytest.raises(WorkerConfigError, match="not found"):
        load_worker_config(tmp_path / "does-not-exist.json")


@pytest.mark.unit
def test_invalid_json_raises_clear_error(tmp_path):
    path = tmp_path / "chiron.config.json"
    path.write_text("{not valid json")
    with pytest.raises(WorkerConfigError, match="not valid JSON"):
        load_worker_config(path)


@pytest.mark.unit
def test_missing_domain_raises_naming_the_domain(tmp_path):
    data = json.loads(json.dumps(_VALID))
    del data["domains"]["news"]
    path = _write_config(tmp_path, data)
    with pytest.raises(WorkerConfigError, match="domains.news"):
        load_worker_config(path)


@pytest.mark.unit
def test_invalid_trigger_raises_naming_the_domain(tmp_path):
    data = json.loads(json.dumps(_VALID))
    data["domains"]["price"]["trigger"] = "bogus"
    path = _write_config(tmp_path, data)
    with pytest.raises(WorkerConfigError, match="domains.price.trigger"):
        load_worker_config(path)


@pytest.mark.unit
def test_missing_seconds_on_interval_trigger_raises(tmp_path):
    data = json.loads(json.dumps(_VALID))
    del data["domains"]["price"]["seconds"]
    path = _write_config(tmp_path, data)
    with pytest.raises(WorkerConfigError, match="domains.price.seconds"):
        load_worker_config(path)


@pytest.mark.unit
def test_missing_rate_limit_on_news_raises(tmp_path):
    data = json.loads(json.dumps(_VALID))
    del data["domains"]["news"]["rate_limit_per_day"]
    path = _write_config(tmp_path, data)
    with pytest.raises(WorkerConfigError, match="domains.news.rate_limit_per_day"):
        load_worker_config(path)


@pytest.mark.unit
def test_mismatched_shared_rate_limits_raises(tmp_path):
    data = json.loads(json.dumps(_VALID))
    data["domains"]["news"]["rate_limit_per_day"] = 10
    path = _write_config(tmp_path, data)
    with pytest.raises(WorkerConfigError, match="must be equal"):
        load_worker_config(path)


@pytest.mark.unit
def test_empty_tickers_raises(tmp_path):
    data = json.loads(json.dumps(_VALID))
    data["tickers"] = []
    path = _write_config(tmp_path, data)
    with pytest.raises(WorkerConfigError, match="tickers"):
        load_worker_config(path)
