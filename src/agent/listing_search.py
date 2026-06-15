from __future__ import annotations

from typing import TYPE_CHECKING

from src.tools.relocation_db import SearchListingsInput

from .state import AgentState

if TYPE_CHECKING:
    from .dependencies import GraphDependencies


def listing_search_node(state: AgentState, deps: "GraphDependencies") -> AgentState:
    if state.intent not in {"search", "replanning", "preference_conflict", "budget_limit"}:
        return state
    if state.requirements is None or state.missing_fields:
        return state

    include_short_term = False
    if state.relocation_case and (
        state.relocation_case.urgency_level == "urgent"
        or state.relocation_case.document_status != "complete"
    ):
        include_short_term = True

    budget_slack_ratio = 1.6 if state.intent in {"preference_conflict", "budget_limit"} else 1.25
    state.candidate_listings = deps.db_tools.search_listings(
        SearchListingsInput(
            city=state.requirements.city,
            move_in_date=state.requirements.move_in_date,
            monthly_budget=state.requirements.monthly_budget,
            budget_currency=state.requirements.budget_currency,
            preferred_districts=state.requirements.preferred_districts,
            rooms_min=state.requirements.rooms_min,
            housing_type=state.requirements.housing_type,
            furnished=state.requirements.furnished,
            pet_count=state.requirements.household.pet_count,
            max_commute_minutes=state.requirements.max_commute_minutes,
            budget_slack_ratio=budget_slack_ratio,
            include_short_term=include_short_term,
        )
    ).listings
    pull_runtime_warnings = getattr(deps.db_tools, "pull_runtime_warnings", None)
    if callable(pull_runtime_warnings):
        state.warnings.extend(pull_runtime_warnings())
    if not state.candidate_listings:
        state.warnings.append("По текущим фильтрам в каталоге не найдено ни одного варианта.")
    return state
