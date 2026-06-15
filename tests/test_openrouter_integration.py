from __future__ import annotations

import os
from pathlib import Path

import pytest

from src.agent.dependencies import GraphDependencies
from src.agent.router import router_node
from src.agent.state import AgentState
from src.db.seed import seed_database
from src.runtime_config import load_agent_runtime_config
from src.tools.calculations import CalculationTools
from src.tools.relocation_db import RelocationDBTools


ROOT_DIR = Path(__file__).resolve().parents[1]
RUNTIME_CONFIG_PATH = ROOT_DIR / "config" / "agent_runtime.json"
ENABLE_FLAG = "RUN_OPENROUTER_INTEGRATION"


def _has_real_api_key(raw_key: str | None) -> bool:
    if not raw_key:
        return False
    lowered = raw_key.strip().lower()
    return not lowered.startswith("paste-")


@pytest.mark.integration
def test_router_uses_live_openrouter_with_repo_runtime_config(monkeypatch, tmp_path):
    if os.getenv(ENABLE_FLAG) != "1":
        pytest.skip(
            f"Set {ENABLE_FLAG}=1 to run live OpenRouter integration tests."
        )
    if not RUNTIME_CONFIG_PATH.exists():
        pytest.skip(f"Missing runtime config: {RUNTIME_CONFIG_PATH}")

    monkeypatch.setenv("AGENT_RUNTIME_CONFIG_PATH", str(RUNTIME_CONFIG_PATH))
    monkeypatch.delenv("AGENT_RUNTIME_CONFIG_JSON", raising=False)

    config = load_agent_runtime_config()
    if config is None:
        pytest.skip("Runtime config could not be loaded.")
    if config.llm_backend not in (None, "openrouter"):
        pytest.skip(
            f"Runtime config backend is `{config.llm_backend}`, expected `openrouter`."
        )
    if not _has_real_api_key(config.openrouter.api_key):
        pytest.skip("Runtime config does not contain a usable OpenRouter API key.")

    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    deps = GraphDependencies(
        db_tools=db_tools,
        calc_tools=CalculationTools(db_tools),
        llm_mode="required",
        llm_backend="openrouter",
    )
    state = AgentState(
        user_message="Подбери 3 варианта аренды в Алматы до 900 USD."
    )

    state = router_node(state, deps)

    assert deps.llm is not None
    assert state.intent == "search"
