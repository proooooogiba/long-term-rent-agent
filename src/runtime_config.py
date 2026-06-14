from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Literal

from dotenv import load_dotenv
from pydantic import BaseModel, Field


ROOT_DIR = Path(__file__).resolve().parents[1]
DEFAULT_AGENT_RUNTIME_CONFIG_PATH = ROOT_DIR / "config" / "agent_runtime.json"


class OpenRouterRuntimeConfig(BaseModel):
    api_key: str | None = None
    model: str | None = None
    app_title: str | None = None
    http_referer: str | None = None


class MCPRuntimeSettings(BaseModel):
    config_path: str | None = None
    include_local_listings: bool | None = None
    providers: list[dict[str, Any]] = Field(default_factory=list)


class AgentRuntimeConfig(BaseModel):
    llm_mode: Literal["off", "auto", "required"] | None = None
    llm_backend: Literal["openrouter", "demo_stub"] | None = None
    openrouter: OpenRouterRuntimeConfig = Field(default_factory=OpenRouterRuntimeConfig)
    mcp: MCPRuntimeSettings = Field(default_factory=MCPRuntimeSettings)


def _resolve_config_path(raw_path: str) -> Path:
    path = Path(raw_path)
    if not path.is_absolute():
        path = ROOT_DIR / path
    return path


def load_agent_runtime_config() -> AgentRuntimeConfig | None:
    load_dotenv(ROOT_DIR / ".env")

    inline_config = os.getenv("AGENT_RUNTIME_CONFIG_JSON")
    if inline_config:
        return AgentRuntimeConfig.model_validate(json.loads(inline_config))

    explicit_path = os.getenv("AGENT_RUNTIME_CONFIG_PATH")
    config_path: Path | None = None

    if explicit_path:
        config_path = _resolve_config_path(explicit_path)
        if not config_path.exists():
            raise FileNotFoundError(
                f"AGENT_RUNTIME_CONFIG_PATH points to missing file: {config_path}"
            )
    elif DEFAULT_AGENT_RUNTIME_CONFIG_PATH.exists():
        config_path = DEFAULT_AGENT_RUNTIME_CONFIG_PATH

    if config_path is None:
        return None

    return AgentRuntimeConfig.model_validate(
        json.loads(config_path.read_text(encoding="utf-8"))
    )


def resolve_llm_mode(default: Literal["off", "auto", "required"] = "auto") -> Literal["off", "auto", "required"]:
    runtime_config = load_agent_runtime_config()
    if runtime_config and runtime_config.llm_mode is not None:
        return runtime_config.llm_mode

    return os.getenv("AGENT_LLM_MODE", default)  # type: ignore[return-value]


def resolve_llm_backend(default: Literal["openrouter", "demo_stub"] = "openrouter") -> Literal["openrouter", "demo_stub"]:
    runtime_config = load_agent_runtime_config()
    if runtime_config and runtime_config.llm_backend is not None:
        return runtime_config.llm_backend

    return os.getenv("AGENT_LLM_BACKEND", default)  # type: ignore[return-value]


def resolve_openrouter_model(default: str) -> str:
    runtime_config = load_agent_runtime_config()
    configured = runtime_config.openrouter.model if runtime_config else None
    return configured or os.getenv("OPENROUTER_MODEL", default)
