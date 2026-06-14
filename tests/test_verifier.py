from __future__ import annotations

from src.agent.dependencies import GraphDependencies
from src.agent.state import AgentState, Household, RentalRequirements
from src.agent.verifier import verifier_node
from src.db.seed import seed_database
from src.tools.calculations import CalculationTools, ScoreListingInput
from src.tools.relocation_db import RelocationDBTools


def _deps(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    return GraphDependencies(db_tools=db_tools, calc_tools=CalculationTools(db_tools), llm_mode="off")


def test_unavailable_listing_is_not_approved(tmp_path):
    deps = _deps(tmp_path)
    requirements = RentalRequirements(city="Минск", move_in_date="2026-06-23", monthly_budget=1000, household=Household(adults=1), rooms_min=1)
    scored = deps.calc_tools.score_listing(ScoreListingInput(listing_id="LS-MIN-017", requirements=requirements))
    state = AgentState(user_message="test", intent="search", requirements=requirements, ranked_listings=[scored])
    state = verifier_node(state, deps)
    assert state.verification_result.status in {"clarification", "rejected"}


def test_non_pet_friendly_listing_fails_for_pet_owner(tmp_path):
    deps = _deps(tmp_path)
    requirements = RentalRequirements(city="Ереван", monthly_budget=1200, household=Household(adults=2, pets=["cat"]), rooms_min=1)
    scored = deps.calc_tools.score_listing(ScoreListingInput(listing_id="LS-EVN-034", requirements=requirements))
    state = AgentState(user_message="test", intent="search", requirements=requirements, ranked_listings=[scored])
    state = verifier_node(state, deps)
    assert "pet_policy_mismatch" in state.verification_result.failed_checks


def test_high_deposit_gets_warning_or_block(tmp_path):
    deps = _deps(tmp_path)
    requirements = RentalRequirements(city="Баку", monthly_budget=980, upfront_budget=2600, household=Household(adults=2, children=1, pets=["dog"]), rooms_min=2)
    scored = deps.calc_tools.score_listing(ScoreListingInput(listing_id="LS-BAK-031", requirements=requirements))
    state = AgentState(user_message="test", intent="search", requirements=requirements, ranked_listings=[scored])
    state = verifier_node(state, deps)
    assert state.verification_result.status in {"approved", "clarification"}
    assert any("депозит" in warning for warning in state.verification_result.warnings)
