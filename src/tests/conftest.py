"""Shared pytest fixtures that prevent CI hangs when API keys are absent."""

import os
from unittest.mock import MagicMock, patch

import pytest


def pytest_configure(config):
    for marker in ("unit", "integration", "smoke"):
        config.addinivalue_line("markers", f"{marker}: {marker}-level tests")


_API_KEY_ENV_VARS = (
    "OPENAI_API_KEY",
    "GOOGLE_API_KEY",
    "ANTHROPIC_API_KEY",
    "XAI_API_KEY",
    "DEEPSEEK_API_KEY",
    "DASHSCOPE_API_KEY",
    "DASHSCOPE_CN_API_KEY",
    "ZHIPU_API_KEY",
    "ZHIPU_CN_API_KEY",
    "MINIMAX_API_KEY",
    "MINIMAX_CN_API_KEY",
    "OPENROUTER_API_KEY",
    "AZURE_OPENAI_API_KEY",
    "ALPHA_VANTAGE_API_KEY",
)


@pytest.fixture(autouse=True)
def _dummy_api_keys(monkeypatch):
    for env_var in _API_KEY_ENV_VARS:
        # `or` not a .get default: an env var present but empty (e.g. a key left
        # blank in a .env copied from .env.example) must still get the placeholder.
        monkeypatch.setenv(env_var, os.environ.get(env_var) or "placeholder")


@pytest.fixture(autouse=True)
def _isolate_config():
    """Reset the global dataflows config before and after each test.

    ``set_config`` merges (it never clears keys absent from the override), so a
    test that sets e.g. ``tool_vendors`` would otherwise leak into later tests
    and make routing behavior order-dependent. Replace the global outright so
    every test starts from a clean DEFAULT_CONFIG.
    """
    import copy

    import chiron.dataflows.config as config_module
    import chiron.default_config as default_config

    config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)
    yield
    config_module._config = copy.deepcopy(default_config.DEFAULT_CONFIG)


@pytest.fixture()
async def cache_pool(monkeypatch):
    """Yield an asyncpg pool against a dedicated *test* Postgres database with
    a clean ``domain_cache`` table, or skip the test if no local Postgres is
    configured.

    Deliberately never touches the real ``POSTGRES_DB``/``TRADINGAGENTS_POSTGRES_DSN``
    a developer has configured for actual chiron_worker/chiron_entrypoint use —
    this fixture's own ``TRUNCATE domain_cache`` previously ran against
    whatever database those pointed at, silently destroying real cached data
    on every local `pytest -m integration` run. ``POSTGRES_DB`` is overridden
    to ``TEST_POSTGRES_DB`` (default ``chiron_test``, a sibling database, not
    a schema/table prefix within the real one) and any explicit
    ``TRADINGAGENTS_POSTGRES_DSN`` override is unset for the duration of the
    fixture, so it can't point tests at a non-test database by accident.
    """
    from chiron_cache.db import _resolve_dsn, create_pool
    from chiron_cache.schema import ensure_schema

    monkeypatch.delenv("TRADINGAGENTS_POSTGRES_DSN", raising=False)
    monkeypatch.setenv("POSTGRES_DB", os.environ.get("TEST_POSTGRES_DB") or "chiron_test")

    try:
        _resolve_dsn()
    except RuntimeError:
        pytest.skip("POSTGRES_USER/PASSWORD are not set — skipping integration test")

    pool = await create_pool()
    async with pool.acquire() as conn:
        await ensure_schema(conn)
        await conn.execute("TRUNCATE domain_cache")
    yield pool
    await pool.close()


@pytest.fixture()
def mock_llm_client():
    client = MagicMock()
    client.get_llm.return_value = MagicMock()
    with patch(
        "chiron.llm_clients.factory.create_llm_client",
        return_value=client,
    ):
        yield client
