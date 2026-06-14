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
            return schema.model_validate({"intent": self._route(self._extract_user_message(user_prompt))})
        if schema is IntakeExtraction:
            return schema.model_validate(self._intake(self._extract_user_message(user_prompt)))
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
        if schema.__name__ == "ClarificationAnswerSections":
            return schema.model_validate(
                {
                    "preface": "stub clarification",
                    "questions": ["Уточни тип жилья."],
                }
            )
        raise AssertionError(f"Unexpected schema: {schema}")

    @staticmethod
    def _extract_user_message(user_prompt: str) -> str:
        marker = "User message:\n"
        return user_prompt.split(marker, 1)[1].split("\n\n", 1)[0]

    @staticmethod
    def _route(message: str) -> str:
        lowered = message.lower()
        if "бюджет" in lowered and ("не 900, а 760" in lowered or "760" in lowered):
            return "budget_limit"
        if "теперь" in lowered or "оставь" in lowered or "пересчитай" in lowered:
            return "replanning"
        return "search"

    @staticmethod
    def _intake(message: str) -> dict[str, object]:
        payloads: dict[str, dict[str, object]] = {
            "Подбери мне аренду в Алматы, бюджет до 900 долларов, езжу в офис почти каждый день, хочу меблированный вариант и без слишком долгой дороги.": {
                "city": "Алматы",
                "monthly_budget": 900,
                "furnished": True,
                "max_commute_minutes": 45,
                "office_dependency": True,
            },
            "Оставь Алматы и ту же офисную локацию, но теперь у меня бюджет не 900, а 760 долларов.": {
                "city": "Алматы",
                "monthly_budget": 760,
                "office_dependency": True,
            },
            "Теперь у нас не одна кошка, а две. Пересчитай вариант для Еревана.": {
                "city": "Ереван",
                "pets": ["cat", "cat"],
                "office_dependency": False,
            },
            "Теперь ищем уже в Ереване, бюджет до 1200 долларов, переезд 2026-07-10, для пары с кошкой.": {
                "city": "Ереван",
                "monthly_budget": 1200,
                "move_in_date": "2026-07-10",
                "adults": 2,
                "pets": ["cat"],
                "office_dependency": False,
            },
            "Нужна квартира в центре Баку, переезд 2026-07-05, бюджет 1400 долларов, для пары, можно без животных.": {
                "city": "Баку",
                "monthly_budget": 1400,
                "move_in_date": "2026-07-05",
                "adults": 2,
                "pets": [],
                "housing_type": "apartment",
                "center_preference": "prefer_center",
                "office_dependency": False,
            },
        }
        return payloads[message]


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


def test_budget_change_triggers_replanning(tmp_path):
    agent = _agent(tmp_path)
    session = AgentSession(agent=agent)
    session.handle_message(
        "Подбери мне аренду в Алматы, бюджет до 900 долларов, езжу в офис почти каждый день, хочу меблированный вариант и без слишком долгой дороги.",
        case_id="R-0001",
    )
    follow = session.handle_message("Оставь Алматы и ту же офисную локацию, но теперь у меня бюджет не 900, а 760 долларов.")
    assert follow.changed_constraints["monthly_budget"]["new"] == 760.0
    assert follow.ranked_listings[0].listing.listing_id == "LS-ALM-029"


def test_adding_pet_excludes_non_pet_friendly_options(tmp_path):
    agent = _agent(tmp_path)
    state = agent.run("Теперь у нас не одна кошка, а две. Пересчитай вариант для Еревана.", case_id="R-0002")
    assert state.ranked_listings[0].listing.listing_id == "LS-EVN-044"
    assert state.ranked_listings[0].listing.pet_friendly is True


def test_city_change_resets_old_recommendations(tmp_path):
    agent = _agent(tmp_path)
    base = agent.run(
        "Подбери мне аренду в Алматы, бюджет до 900 долларов, езжу в офис почти каждый день, хочу меблированный вариант и без слишком долгой дороги.",
        case_id="R-0001",
    )
    follow = agent.run(
        "Теперь ищем уже в Ереване, бюджет до 1200 долларов, переезд 2026-07-10, для пары с кошкой.",
        previous_state=base,
    )
    assert follow.changed_constraints["city"]["new"] == "Ереван"
    assert all(not item.listing.listing_id.startswith("LS-ALM") for item in follow.ranked_listings[:3])


def test_center_preference_comes_from_db_district_flags(tmp_path):
    agent = _agent(tmp_path)
    state = agent.run(
        "Нужна квартира в центре Баку, переезд 2026-07-05, бюджет 1400 долларов, для пары, можно без животных.",
    )
    assert state.requirements is not None
    assert state.requirements.preferred_districts == ["DST-BAK-01"]
