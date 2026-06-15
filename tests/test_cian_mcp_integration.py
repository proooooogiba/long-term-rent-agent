from __future__ import annotations

import importlib.util
import os
from pathlib import Path

import pytest

from src.tools.mcp_listings import CompositeRelocationDBTools, build_listing_data_tools
from src.tools.relocation_db import RelocationDBTools, SearchListingsInput


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNTIME_CONFIG_PATH = ROOT_DIR / "config" / "agent_runtime.json"
ENABLE_FLAG = "RUN_CIAN_MCP_INTEGRATION"


@pytest.mark.integration
def test_live_cian_provider_returns_moscow_listings_for_usd_budget(monkeypatch):
    if os.getenv(ENABLE_FLAG) != "1":
        pytest.skip(f"Set {ENABLE_FLAG}=1 to run live Cian MCP integration tests.")
    if not RUNTIME_CONFIG_PATH.exists():
        pytest.skip(f"Missing runtime config: {RUNTIME_CONFIG_PATH}")
    if importlib.util.find_spec("mcp") is None:
        pytest.skip("Python package `mcp` is not installed in the current environment.")

    monkeypatch.setenv("AGENT_RUNTIME_CONFIG_PATH", str(RUNTIME_CONFIG_PATH))
    monkeypatch.delenv("AGENT_MCP_CONFIG_JSON", raising=False)
    monkeypatch.delenv("AGENT_MCP_CONFIG_PATH", raising=False)

    db_tools = RelocationDBTools(ROOT_DIR / "data" / "relocation" / "relocation.sqlite")
    tools = build_listing_data_tools(db_tools)
    if not isinstance(tools, CompositeRelocationDBTools):
        pytest.skip("Runtime config did not build MCP-backed listing tools.")

    result = tools.search_listings(
        SearchListingsInput(
            city="Москва",
            monthly_budget=2000,
            budget_currency="USD",
            housing_type="apartment",
        )
    )
    warnings = tools.pull_runtime_warnings()

    assert warnings == []
    assert len(result.listings) > 0
    assert all(listing.city == "Москва" for listing in result.listings[:5])
    assert all(listing.currency == "USD" for listing in result.listings[:5])
