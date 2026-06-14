from __future__ import annotations

from datetime import date

from src.agent.state import (
    AgentState,
    DistrictRecommendation,
    Household,
    Listing,
    RelocationService,
    RentalRequirements,
    ScoredListing,
    UpfrontCostEstimate,
    VerificationResult,
)
from src.evals.metrics import evaluate_case


def _scored_listing(listing_id: str, district_id: str) -> ScoredListing:
    return ScoredListing(
        listing=Listing(
            listing_id=listing_id,
            city="Алматы",
            country="Казахстан",
            district_id=district_id,
            district_name="Бостандыкский",
            title="2-комнатная квартира",
            property_type="apartment",
            monthly_rent=850,
            area_sqm=48,
            rooms=2,
            available_from=date(2026, 7, 1),
            pet_friendly=True,
        ),
        total_score=0.91,
        pros=["Подходит по бюджету"],
        cons=["Небольшой компромисс по площади"],
        estimated_upfront_cost=UpfrontCostEstimate(
            listing_id=listing_id,
            first_month=850,
            deposit=850,
            agency_fee=0,
            move_in_fee=0,
            utilities_reserve=100,
            total=1800,
        ),
    )


def test_evaluate_case_checks_expected_listing_district_and_service_entities():
    case = {
        "category": "search",
        "expected_outcome_type": "recommendation",
        "expected_entities": {
            "listing_id": "LS-ALM-014",
            "district_id": "DST-ALM-02",
            "service_id": "SV-TEMP-001",
        },
    }
    state = AgentState(
        user_message="Подбери вариант.",
        intent="search",
        requirements=RentalRequirements(
            city="Алматы",
            move_in_date=date(2026, 7, 1),
            monthly_budget=900,
            household=Household(adults=1),
            rooms_min=1,
        ),
        ranked_listings=[_scored_listing("LS-ALM-014", "DST-ALM-02")],
        relocation_services=[
            RelocationService(
                service_id="SV-TEMP-001",
                city="Алматы",
                country="Казахстан",
                service_type="temporary_housing",
                name="Temporary stay support",
                cost=250,
                description="Помощь с временным размещением.",
            )
        ],
        verification_result=VerificationResult(status="approved"),
        final_answer="Почему подходит:\nРиски/компромиссы:",
    )

    metrics = evaluate_case(case, state, reference_costs={"LS-ALM-014": 1800})

    assert metrics.expected_entities_accuracy == 1.0


def test_evaluate_case_accepts_expected_district_from_district_recommendations():
    case = {
        "category": "clarification",
        "expected_outcome_type": "clarification",
        "expected_entities": {"district_id": "DST-TAS-02"},
    }
    state = AgentState(
        user_message="Что меняется?",
        intent="clarification",
        requirements=RentalRequirements(
            city="Ташкент",
            move_in_date=date(2026, 7, 1),
            monthly_budget=1300,
            household=Household(adults=2, children=1),
            rooms_min=2,
        ),
        district_recommendations=[
            DistrictRecommendation(
                district_id="DST-TAS-02",
                city="Ташкент",
                rationale="Лучший баланс по дороге до офиса.",
                estimated_rent_range="900-1200 USD",
                estimated_commute_minutes=28,
            )
        ],
        verification_result=VerificationResult(status="clarification"),
    )

    metrics = evaluate_case(case, state, reference_costs={})

    assert metrics.expected_entities_accuracy == 1.0


def test_evaluate_case_tracks_sources_marker_for_info_answers():
    case = {
        "category": "info",
        "expected_outcome_type": "info",
        "expected_entities": {},
    }
    with_sources = AgentState(
        user_message="Какие правила?",
        intent="info",
        verification_result=VerificationResult(status="approved"),
        final_answer="Краткий ответ.\n\nИсточники:\n- https://example.test/rules",
    )
    without_sources = AgentState(
        user_message="Какие правила?",
        intent="info",
        verification_result=VerificationResult(status="approved"),
        final_answer="Краткий ответ без ссылок.",
    )

    metrics_with_sources = evaluate_case(case, with_sources, reference_costs={})
    metrics_without_sources = evaluate_case(case, without_sources, reference_costs={})

    assert metrics_with_sources.info_answer_has_sources == 1.0
    assert metrics_without_sources.info_answer_has_sources == 0.0
