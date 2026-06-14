from __future__ import annotations

from src.agent.dependencies import GraphDependencies
from src.agent.graph import AgentGraph, AgentSession, RelocationAgent
from src.agent.message_understanding import IntakeExtraction, RouterDecision
from src.agent.replanner import ReplanningAssessment
from src.db.seed import seed_database
from src.tools.calculations import CalculationTools
from src.tools.relocation_db import RelocationDBTools


class ScenarioLLM:
    def extract_json(self, system_prompt: str, user_prompt: str, schema):
        if schema is RouterDecision:
            return schema.model_validate({"intent": "search"})
        if schema is IntakeExtraction:
            return schema.model_validate(
                {
                    "city": "Алматы",
                    "monthly_budget": 900,
                    "furnished": True,
                    "max_commute_minutes": 45,
                    "office_dependency": True,
                }
            )
        if schema is ReplanningAssessment:
            return schema.model_validate({"impact_tags": [], "notes": []})
        if schema.__name__ == "RecommendationAnswerSections":
            return schema.model_validate(
                {
                    "summary": "stub summary",
                    "important_notes": [],
                    "alternatives": [],
                    "clarification_lines": [],
                }
            )
        raise AssertionError(f"Unexpected schema: {schema}")


def _agent(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    deps = GraphDependencies(
        db_tools=db_tools,
        calc_tools=CalculationTools(db_tools),
        llm=ScenarioLLM(),
        llm_mode="required",
    )
    return RelocationAgent(graph=AgentGraph(deps=deps))


def test_session_stores_trace_for_last_run(tmp_path):
    agent = _agent(tmp_path)
    session = AgentSession(agent=agent)
    live_updates: list[str] = []

    session.handle_message(
        "Подбери мне аренду в Алматы, бюджет до 900 долларов, езжу в офис почти каждый день, хочу меблированный вариант и без слишком долгой дороги.",
        case_id="R-0001",
        trace_callback=live_updates.append,
    )

    assert [step.node for step in session.last_trace] == [
        "router",
        "intake",
        "rag_policy",
        "district_advisor",
        "listing_search",
        "scoring",
        "verifier",
        "replanner",
        "final_composer",
    ]
    assert session.last_trace[-1].summary
    assert any(update.startswith("Router:") for update in live_updates)
