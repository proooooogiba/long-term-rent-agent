from __future__ import annotations

from src.agent.dependencies import GraphDependencies
from src.agent.intake import intake_node
from src.agent.replanner import replanner_node
from src.agent.router import router_node
from src.agent.state import AgentState, Household, RentalRequirements
from src.db.seed import seed_database
from src.tools.calculations import CalculationTools
from src.tools.relocation_db import RelocationDBTools


class StubStructuredLLM:
    def __init__(self, payloads: dict[str, dict[str, object]]):
        self.payloads = payloads

    def extract_json(self, system_prompt: str, user_prompt: str, schema):
        return schema.model_validate(self.payloads[schema.__name__])


def _deps(tmp_path, payloads: dict[str, dict[str, object]]) -> GraphDependencies:
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    return GraphDependencies(
        db_tools=db_tools,
        calc_tools=CalculationTools(db_tools),
        llm=StubStructuredLLM(payloads),
        llm_mode="required",
    )


def test_router_uses_llm_decision_instead_of_keyword_heuristic(tmp_path):
    deps = _deps(tmp_path, {"RouterDecision": {"intent": "info", "rationale": "stubbed"}})
    state = AgentState(user_message="Подбери мне аренду в Алматы до 900 долларов.")

    state = router_node(state, deps)

    assert state.intent == "info"


def test_intake_uses_llm_extraction_without_regex_overlay(tmp_path):
    deps = _deps(
        tmp_path,
        {
            "IntakeExtraction": {
                "city": "Минск",
                "country": None,
                "move_in_date": "2026-07-15",
                "monthly_budget": 915,
                "upfront_budget": 2100,
                "adults": 2,
                "children": 1,
                "pets": ["cat", "cat"],
                "preferred_districts": None,
                "office_zone": "north-hub",
                "max_commute_minutes": 35,
                "rooms_min": 2,
                "housing_type": "apartment",
                "furnished": True,
                "elevator": True,
                "floor_max": 8,
                "school_requirement": True,
                "lease_months": 6,
                "has_passport": False,
                "employer_support": True,
                "citizenship": "Россия",
                "document_status": "incomplete_docs",
                "center_preference": "unspecified",
                "office_dependency": True,
            }
        },
    )
    state = AgentState(user_message="Формулировка может быть любой.", intent="search")

    state = intake_node(state, deps)

    assert state.requirements is not None
    assert state.requirements.city == "Минск"
    assert state.requirements.country == "Беларусь"
    assert state.requirements.monthly_budget == 915
    assert state.requirements.upfront_budget == 2100
    assert state.requirements.household.adults == 2
    assert state.requirements.household.children == 1
    assert state.requirements.household.pets == ["cat", "cat"]
    assert state.requirements.office_zone == "north-hub"
    assert state.requirements.max_commute_minutes == 35
    assert state.requirements.rooms_min == 2
    assert state.requirements.lease_months == 6
    assert state.requirements.has_passport is False
    assert state.requirements.employer_support is True
    assert state.requirements.citizenship == "Россия"
    assert "document_status:incomplete_docs" in state.requirements.notes
    assert state.missing_fields == []


def test_replanner_uses_llm_assessment_for_notes_and_tags(tmp_path):
    deps = _deps(
        tmp_path,
        {
            "ReplanningAssessment": {
                "impact_tags": ["budget_tightened", "shortlist_changed"],
                "notes": [
                    "Бюджет стал строже, поэтому часть прежних вариантов выбыла.",
                    "Из топа исчезли прошлые дорогие варианты.",
                ],
            }
        },
    )
    state = AgentState(
        user_message="Бюджет снижаем.",
        previous_requirements=RentalRequirements(
            city="Алматы",
            monthly_budget=900,
            household=Household(adults=1),
        ),
        requirements=RentalRequirements(
            city="Алматы",
            monthly_budget=760,
            household=Household(adults=1),
        ),
    )

    state = replanner_node(state, deps)

    assert state.changed_constraints["monthly_budget"]["new"] == 760
    assert state.replanning_tags == ["budget_tightened", "shortlist_changed"]
    assert state.replanning_notes == [
        "Бюджет стал строже, поэтому часть прежних вариантов выбыла.",
        "Из топа исчезли прошлые дорогие варианты.",
    ]
