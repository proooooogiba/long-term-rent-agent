from __future__ import annotations

from src.agent.dependencies import GraphDependencies
from datetime import date

from src.agent.final_composer import final_composer_node
from src.agent.state import (
    AgentState,
    FinalRecommendation,
    Listing,
    PolicyChunk,
    ScoredListing,
    UpfrontCostEstimate,
    VerificationResult,
)
from src.db.seed import seed_database
from src.tools.relocation_db import GetCountryProfileInput, RelocationDBTools


def test_info_answer_includes_reference_links(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    country_profile = db_tools.get_country_profile(GetCountryProfileInput(country="Армения"))

    deps = GraphDependencies(db_tools=db_tools, llm_mode="off")
    state = AgentState(
        user_message="Какие базовые правила по ВНЖ в Армении?",
        intent="info",
        country_profile=country_profile,
        retrieved_policy_chunks=[
            PolicyChunk(
                source="07_cis_migration_basics.md",
                heading="Армения: residence status и гражданство",
                text="Источники: https://migration.e-gov.am/en/service/residency_application/info",
            )
        ],
    )

    state = final_composer_node(state, deps)

    assert state.final_answer is not None
    assert "Источники:" in state.final_answer
    assert "https://migration.e-gov.am/en/service/residency_application/info" in state.final_answer


def test_clarification_answer_uses_local_fallback_when_llm_unavailable(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    deps = GraphDependencies(db_tools=db_tools, llm_mode="off")
    state = AgentState(
        user_message="Подбери аренду, но деталей пока мало.",
        intent="clarification",
        missing_fields=["city"],
        verification_result=VerificationResult(
            status="clarification",
            required_user_clarifications=["в каком городе искать жильё"],
        ),
    )

    state = final_composer_node(state, deps)

    assert state.final_answer is not None
    assert "Чтобы продолжить подбор" in state.final_answer
    assert "в каком городе искать жильё" in state.final_answer


def test_recommendation_answer_renders_markdown_listing_links(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    deps = GraphDependencies(db_tools=db_tools, llm_mode="off")
    scored = ScoredListing(
        listing=Listing(
            listing_id="cian:301578186",
            city="Москва",
            country="Россия",
            district_id="cian:district:1",
            district_name="улица Екатерины Будановой, 5",
            title="1-комнатная квартира",
            property_type="apartment",
            monthly_rent=1500,
            currency="USD",
            deposit_months=1.0,
            agency_fee=0.0,
            move_in_fee=0.0,
            utilities_monthly=0.0,
            area_sqm=40,
            rooms=1,
            available_from=date(2026, 7, 7),
            notes=["source:cian", "url:https://www.cian.ru/rent/flat/301578186/"],
        ),
        total_score=0.91,
        pros=["Подходит по бюджету"],
        cons=[],
        constraint_violations=[],
        estimated_upfront_cost=UpfrontCostEstimate(
            listing_id="cian:301578186",
            first_month=1500,
            deposit=1500,
            agency_fee=0,
            move_in_fee=0,
            utilities_reserve=0,
            total=3000,
            currency="USD",
        ),
    )
    state = AgentState(
        user_message="Подбери варианты по Москве.",
        intent="search",
        ranked_listings=[scored],
        verification_result=VerificationResult(status="approved"),
        final_recommendation=FinalRecommendation(summary=""),
    )

    state = final_composer_node(state, deps)

    assert state.final_answer is not None
    assert "[улица Екатерины Будановой, 5, Москва](https://www.cian.ru/rent/flat/301578186/)" in state.final_answer
