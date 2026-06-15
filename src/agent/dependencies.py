from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal, cast

from dotenv import load_dotenv

from src.runtime_config import resolve_llm_backend, resolve_llm_mode
from src.tools.agent_memory import AgentMemoryStore
from src.tools.calculations import CalculationTools
from src.tools.contracts import RelocationToolsProtocol
from src.tools.mcp_listings import build_listing_data_tools
from src.tools.policy_search import PolicySearchTool
from src.tools.relocation_db import RelocationDBTools

from .demo_llm import DemoStructuredLLM
from .llm import OpenRouterStructuredLLM, StructuredLLM


@dataclass
class GraphDependencies:
    db_tools: RelocationToolsProtocol = field(default_factory=RelocationDBTools)
    policy_tool: PolicySearchTool = field(default_factory=PolicySearchTool)
    calc_tools: CalculationTools | None = None
    llm: StructuredLLM | None = None
    llm_mode: Literal["off", "auto", "required"] | None = None
    llm_backend: Literal["openrouter", "demo_stub"] | None = None
    memory_store: AgentMemoryStore | None = None

    def __post_init__(self) -> None:
        project_env = Path(__file__).resolve().parents[2] / ".env"
        if project_env.exists():
            load_dotenv(dotenv_path=project_env, override=False)
        self.db_tools = build_listing_data_tools(self.db_tools)
        if self.llm_mode is None:
            self.llm_mode = cast(Literal["off", "auto", "required"], resolve_llm_mode("auto"))
        if self.llm_backend is None:
            self.llm_backend = cast(Literal["openrouter", "demo_stub"], resolve_llm_backend("openrouter"))
        if self.calc_tools is None:
            self.calc_tools = CalculationTools(self.db_tools)
        if self.memory_store is None:
            db_path = getattr(self.db_tools, "db_path", None)
            if db_path is None and hasattr(self.db_tools, "local_db"):
                db_path = getattr(self.db_tools.local_db, "db_path", None)
            if db_path is not None:
                self.memory_store = AgentMemoryStore(db_path)
        if self.llm is None and self.llm_mode != "off":
            if self.llm_backend == "demo_stub":
                self.llm = DemoStructuredLLM()
                return
            try:
                self.llm = OpenRouterStructuredLLM()
            except ValueError:
                if self.llm_mode == "required":
                    raise
                self.llm = None
