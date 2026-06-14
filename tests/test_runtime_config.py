from __future__ import annotations

import json

from src.runtime_config import (
    load_agent_runtime_config,
    resolve_llm_backend,
    resolve_llm_mode,
    resolve_openrouter_model,
)
from src.tools.mcp_listings import load_mcp_runtime_config


def test_runtime_config_reads_openrouter_settings_from_json(tmp_path, monkeypatch):
    runtime_path = tmp_path / "agent_runtime.json"
    runtime_path.write_text(
        json.dumps(
            {
                "llm_mode": "auto",
                "llm_backend": "demo_stub",
                "openrouter": {
                    "api_key": "test-key",
                    "model": "openrouter/test-model",
                    "app_title": "Test App",
                    "http_referer": "https://example.test",
                },
                "mcp": {},
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("AGENT_RUNTIME_CONFIG_PATH", str(runtime_path))
    monkeypatch.delenv("AGENT_RUNTIME_CONFIG_JSON", raising=False)

    config = load_agent_runtime_config()

    assert config is not None
    assert config.llm_backend == "demo_stub"
    assert config.openrouter.api_key == "test-key"
    assert config.openrouter.model == "openrouter/test-model"
    assert resolve_llm_mode("required") == "auto"
    assert resolve_llm_backend("openrouter") == "demo_stub"
    assert resolve_openrouter_model("fallback-model") == "openrouter/test-model"


def test_mcp_runtime_can_be_loaded_via_agent_runtime_config(tmp_path, monkeypatch):
    runtime_path = tmp_path / "agent_runtime.json"

    runtime_path.write_text(
        json.dumps(
            {
                "llm_mode": "required",
                "openrouter": {"api_key": "", "model": "demo-model"},
                "mcp": {
                    "include_local_listings": True,
                    "providers": [
                        {
                            "provider_id": "demo",
                            "enabled": True,
                            "transport": {
                                "kind": "stdio",
                                "command": "demo-mcp"
                            }
                        }
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("AGENT_RUNTIME_CONFIG_PATH", str(runtime_path))
    monkeypatch.delenv("AGENT_RUNTIME_CONFIG_JSON", raising=False)
    monkeypatch.delenv("AGENT_MCP_CONFIG_JSON", raising=False)
    monkeypatch.delenv("AGENT_MCP_CONFIG_PATH", raising=False)

    config = load_mcp_runtime_config()

    assert config is not None
    assert config.providers[0].provider_id == "demo"
    assert config.providers[0].transport.command == "demo-mcp"


def test_mcp_runtime_prefers_inline_providers_over_runtime_config_path(tmp_path, monkeypatch):
    mcp_path = tmp_path / "mcp_connectors.json"
    runtime_path = tmp_path / "agent_runtime.json"

    mcp_path.write_text(
        json.dumps(
            {
                "include_local_listings": False,
                "providers": [
                    {
                        "provider_id": "path-based",
                        "enabled": True,
                        "transport": {
                            "kind": "stdio",
                            "command": "path-mcp"
                        }
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    runtime_path.write_text(
        json.dumps(
            {
                "mcp": {
                    "config_path": str(mcp_path),
                    "include_local_listings": True,
                    "providers": [
                        {
                            "provider_id": "inline",
                            "enabled": True,
                            "transport": {
                                "kind": "stdio",
                                "command": "inline-mcp"
                            }
                        }
                    ]
                }
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("AGENT_RUNTIME_CONFIG_PATH", str(runtime_path))
    monkeypatch.delenv("AGENT_RUNTIME_CONFIG_JSON", raising=False)
    monkeypatch.delenv("AGENT_MCP_CONFIG_JSON", raising=False)
    monkeypatch.delenv("AGENT_MCP_CONFIG_PATH", raising=False)

    config = load_mcp_runtime_config()

    assert config is not None
    assert config.include_local_listings is True
    assert config.providers[0].provider_id == "inline"
