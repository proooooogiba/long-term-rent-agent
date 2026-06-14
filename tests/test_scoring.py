from __future__ import annotations

from src.agent.state import Household, RentalRequirements
from src.db.seed import seed_database
from src.tools.calculations import CalculationTools, ScoreListingInput
from src.tools.relocation_db import RelocationDBTools


def _calc(tmp_path):
    db_path = seed_database(tmp_path / "relocation.sqlite")
    db_tools = RelocationDBTools(db_path)
    return CalculationTools(db_tools)


def test_budget_fit_is_high_for_budget_listing(tmp_path):
    calc = _calc(tmp_path)
    requirements = RentalRequirements(city="Алматы", monthly_budget=900, household=Household(adults=1), rooms_min=1)
    scored = calc.score_listing(ScoreListingInput(listing_id="LS-ALM-014", requirements=requirements))
    assert scored.sub_scores["budget_fit"] > 0.9


def test_over_budget_listing_gets_constraint_violation(tmp_path):
    calc = _calc(tmp_path)
    requirements = RentalRequirements(city="Алматы", monthly_budget=760, household=Household(adults=1), rooms_min=1)
    scored = calc.score_listing(ScoreListingInput(listing_id="LS-ALM-014", requirements=requirements))
    assert "monthly_budget_exceeded" in scored.constraint_violations


def test_pet_friendly_is_checked_correctly(tmp_path):
    calc = _calc(tmp_path)
    requirements = RentalRequirements(city="Ереван", monthly_budget=1200, household=Household(adults=2, pets=["cat", "cat"]), rooms_min=1)
    scored = calc.score_listing(ScoreListingInput(listing_id="LS-EVN-044", requirements=requirements))
    assert scored.sub_scores["pet_policy_fit"] == 1.0
