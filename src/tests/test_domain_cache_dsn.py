"""Unit tests for chiron_cache.db's DSN resolution."""

import pytest

from chiron_cache.db import _resolve_dsn

_POSTGRES_ENV_VARS = (
    "TRADINGAGENTS_POSTGRES_DSN",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_DB",
    "POSTGRES_HOST",
    "POSTGRES_PORT",
)


@pytest.fixture(autouse=True)
def _clear_postgres_env(monkeypatch):
    for name in _POSTGRES_ENV_VARS:
        monkeypatch.delenv(name, raising=False)


@pytest.mark.unit
def test_explicit_dsn_wins_over_parts(monkeypatch):
    monkeypatch.setenv("TRADINGAGENTS_POSTGRES_DSN", "postgresql://explicit/dsn")
    monkeypatch.setenv("POSTGRES_USER", "u")
    monkeypatch.setenv("POSTGRES_PASSWORD", "p")
    monkeypatch.setenv("POSTGRES_DB", "d")

    assert _resolve_dsn() == "postgresql://explicit/dsn"


@pytest.mark.unit
def test_dsn_composed_from_parts_with_default_host_and_port(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "sapium")
    monkeypatch.setenv("POSTGRES_PASSWORD", "t0p_s3cr3t")
    monkeypatch.setenv("POSTGRES_DB", "chiron")

    assert _resolve_dsn() == "postgresql://sapium:t0p_s3cr3t@localhost:5432/chiron"


@pytest.mark.unit
def test_dsn_composed_from_parts_honors_host_and_port_override(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "sapium")
    monkeypatch.setenv("POSTGRES_PASSWORD", "t0p_s3cr3t")
    monkeypatch.setenv("POSTGRES_DB", "chiron")
    monkeypatch.setenv("POSTGRES_HOST", "postgres")
    monkeypatch.setenv("POSTGRES_PORT", "6543")

    assert _resolve_dsn() == "postgresql://sapium:t0p_s3cr3t@postgres:6543/chiron"


@pytest.mark.unit
def test_missing_dsn_and_parts_raises_clear_error():
    with pytest.raises(RuntimeError, match="TRADINGAGENTS_POSTGRES_DSN"):
        _resolve_dsn()


@pytest.mark.unit
def test_partial_parts_without_dsn_raises_clear_error(monkeypatch):
    monkeypatch.setenv("POSTGRES_USER", "sapium")
    # POSTGRES_PASSWORD and POSTGRES_DB left unset.

    with pytest.raises(RuntimeError, match="TRADINGAGENTS_POSTGRES_DSN"):
        _resolve_dsn()
