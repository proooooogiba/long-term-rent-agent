from __future__ import annotations

import json
import sqlite3

from src.agent.dependencies import GraphDependencies
from src.agent.graph import AgentGraph, RelocationAgent
from src.agent.message_understanding import IntakeExtraction, RouterDecision
from src.agent.replanner import ReplanningAssessment
from src.db.seed import seed_database
from src.tools.calculations import CalculationTools
from src.tools.relocation_db import RelocationDBTools


class SequenceStructuredLLM:
    def __init__(self, payloads: dict[str, list[dict[str, object]]]):
        self.payloads = {key: list(values) for key, values in payloads.items()}

    def extract_json(self, system_prompt: str, user_prompt: str, schema):
        if schema is RouterDecision:
            return schema.model_validate(self.payloads["RouterDecision"].pop(0))
        if schema is IntakeExtraction:
            return schema.model_validate(self.payloads["IntakeExtraction"].pop(0))
        if schema is ReplanningAssessment:
            return schema.model_validate(self.payloads["ReplanningAssessment"].pop(0))
        if schema.__name__ == "RecommendationAnswerSections":
            return schema.model_validate(self.payloads["RecommendationAnswerSections"].pop(0))
        if schema.__name__ == "ClarificationAnswerSections":
            return schema.model_validate(
                {"preface": "Нужно уточнение.", "questions": ["уточните параметры поиска"]}
            )
        if schema.__name__ == "EscalationAnswerSections":
            return schema.model_validate(
                {
                    "reason_summary": "Кейс требует ручной проверки.",
                    "reasons": ["demo"],
                    "preparations": ["demo"],
                }
            )
        raise AssertionError(f"Unexpected schema: {schema}")


def _agent(tmp_path, payloads: dict[str, list[dict[str, object]]]) -> tuple[RelocationAgent, RelocationDBTools]:
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    deps = GraphDependencies(
        db_tools=db_tools,
        calc_tools=CalculationTools(db_tools),
        llm=SequenceStructuredLLM(payloads),
        llm_mode="required",
    )
    return RelocationAgent(graph=AgentGraph(deps=deps)), db_tools


def test_agent_persists_case_memory_and_writes_back_preferences(tmp_path):
    agent, db_tools = _agent(
        tmp_path,
        {
            "RouterDecision": [{"intent": "search"}],
            "IntakeExtraction": [
                {
                    "city": "Алматы",
                    "monthly_budget": 900,
                    "rooms_min": 1,
                    "furnished": True,
                    "max_commute_minutes": 40,
                    "preferred_districts": ["DST-ALM-02"],
                    "office_dependency": True,
                }
            ],
            "ReplanningAssessment": [{"impact_tags": [], "notes": []}],
            "RecommendationAnswerSections": [
                {
                    "summary": "Лучший текущий вариант найден.",
                    "important_notes": [],
                    "alternatives": [],
                    "clarification_lines": [],
                }
            ],
        },
    )

    state = agent.run("Подбери 2-комнатную квартиру в Алматы.", case_id="R-0001")

    assert state.final_recommendation is not None
    with sqlite3.connect(db_tools.db_path) as connection:
        connection.row_factory = sqlite3.Row
        memory_row = connection.execute(
            "SELECT * FROM agent_case_memory WHERE case_id = ?",
            ("R-0001",),
        ).fetchone()
        preference_row = connection.execute(
            "SELECT * FROM client_preferences WHERE client_id = ?",
            ("CL-001",),
        ).fetchone()
        case_row = connection.execute(
            "SELECT notes FROM relocation_cases WHERE case_id = ?",
            ("R-0001",),
        ).fetchone()

    assert memory_row is not None
    assert memory_row["last_verification_status"] == "approved"
    assert preference_row is not None
    assert preference_row["rooms_min"] == 1
    assert preference_row["max_commute_minutes"] == 40
    assert json.loads(preference_row["preferred_districts"]) == ["DST-ALM-02"]
    assert "Updated from agent memory" in preference_row["comments"]
    assert any(
        note.startswith("agent_memory_summary:")
        for note in json.loads(case_row["notes"])
    )


def test_new_agent_session_loads_persistent_memory_for_replanning(tmp_path):
    first_agent, db_tools = _agent(
        tmp_path,
        {
            "RouterDecision": [{"intent": "search"}],
            "IntakeExtraction": [
                {
                    "city": "Алматы",
                    "monthly_budget": 900,
                    "furnished": True,
                    "max_commute_minutes": 45,
                    "office_dependency": True,
                }
            ],
            "ReplanningAssessment": [{"impact_tags": [], "notes": []}],
            "RecommendationAnswerSections": [
                {
                    "summary": "Первичный shortlist собран.",
                    "important_notes": [],
                    "alternatives": [],
                    "clarification_lines": [],
                }
            ],
        },
    )
    first_agent.run("Подбери варианты в Алматы.", case_id="R-0001")

    replanning_db_tools = RelocationDBTools(db_tools.db_path)
    second_deps = GraphDependencies(
        db_tools=replanning_db_tools,
        calc_tools=CalculationTools(replanning_db_tools),
        llm=SequenceStructuredLLM(
            {
                "RouterDecision": [{"intent": "replanning"}],
                "IntakeExtraction": [
                    {
                        "monthly_budget": 760,
                        "center_preference": "center_not_required",
                        "office_dependency": False,
                    }
                ],
                "ReplanningAssessment": [
                    {
                        "impact_tags": ["budget_tightened", "shortlist_changed"],
                        "notes": ["Бюджет снизился, поэтому shortlist пересобран."],
                    }
                ],
                "RecommendationAnswerSections": [
                    {
                        "summary": "После снижения бюджета shortlist обновлён.",
                        "important_notes": [],
                        "alternatives": [],
                        "clarification_lines": [],
                    }
                ],
            }
        ),
        llm_mode="required",
    )
    second_agent = RelocationAgent(graph=AgentGraph(second_deps))

    state = second_agent.run("Снизим бюджет до 760 и центр не обязателен.", case_id="R-0001")

    assert state.persistent_memory_loaded is True
    assert state.previous_requirements is not None
    assert state.previous_requirements.monthly_budget == 900
    assert state.changed_constraints["monthly_budget"]["old"] == 900
    assert state.changed_constraints["monthly_budget"]["new"] == 760
    assert state.replanning_tags == ["budget_tightened", "shortlist_changed"]
