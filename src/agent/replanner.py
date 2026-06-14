from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, Literal

from pydantic import BaseModel, Field

from .llm import require_structured_llm
from .state import AgentState

if TYPE_CHECKING:
    from .dependencies import GraphDependencies


class ReplanningAssessment(BaseModel):
    impact_tags: list[
        Literal[
            "city_reset",
            "budget_tightened",
            "budget_relaxed",
            "availability_window_changed",
            "commute_constraint_changed",
            "household_changed",
            "pet_policy_changed",
            "document_risk_changed",
            "shortlist_changed",
        ]
    ] = Field(default_factory=list)
    notes: list[str] = Field(default_factory=list)


def _changed(old: Any, new: Any) -> bool:
    return old != new


def _build_changes(state: AgentState) -> dict[str, dict[str, Any]]:
    if state.requirements is None or state.previous_requirements is None:
        return {}

    old = state.previous_requirements
    new = state.requirements
    changes: dict[str, dict[str, Any]] = {}

    for field in [
        "city",
        "country",
        "move_in_date",
        "monthly_budget",
        "upfront_budget",
        "preferred_districts",
        "max_commute_minutes",
        "rooms_min",
        "furnished",
        "school_requirement",
        "lease_months",
        "has_passport",
        "employer_support",
    ]:
        old_value = getattr(old, field)
        new_value = getattr(new, field)
        if _changed(old_value, new_value):
            changes[field] = {"old": old_value, "new": new_value}

    if old.household.model_dump() != new.household.model_dump():
        changes["household"] = {
            "old": old.household.model_dump(),
            "new": new.household.model_dump(),
        }

    return changes


def _build_shortlist_delta(state: AgentState) -> tuple[list[str], list[str], list[str]]:
    previous_ids = [item.listing.listing_id for item in state.previous_ranked_listings[:3]]
    current_ids = [item.listing.listing_id for item in state.ranked_listings[:3]]
    dropped_ids = [listing_id for listing_id in previous_ids if listing_id not in current_ids]
    return previous_ids, current_ids, dropped_ids


def _analyze_with_llm(
    state: AgentState,
    deps: "GraphDependencies",
    changes: dict[str, dict[str, Any]],
    previous_ids: list[str],
    current_ids: list[str],
    dropped_ids: list[str],
) -> ReplanningAssessment:
    if state.requirements is None or state.previous_requirements is None:
        return ReplanningAssessment()

    llm = require_structured_llm(deps.llm, "Replanning analysis")

    payload = {
        "user_message": state.user_message,
        "changed_constraints": changes,
        "previous_requirements": state.previous_requirements.model_dump(mode="json"),
        "current_requirements": state.requirements.model_dump(mode="json"),
        "previous_top_listing_ids": previous_ids,
        "current_top_listing_ids": current_ids,
        "dropped_listing_ids": dropped_ids,
    }
    system_prompt = (
        "You analyze how a relocation housing search should be replanned after the user's requirements changed. "
        "Use only the provided context. "
        "Classify the impact using zero or more impact_tags from the allowed enum values. "
        "Write concise Russian notes only when there is a real user-visible consequence. "
        "Do not invent facts about listings, budgets, or legal status beyond the context."
    )
    try:
        return llm.extract_json(
            system_prompt=system_prompt,
            user_prompt=f"Context JSON:\n{json.dumps(payload, ensure_ascii=False, indent=2, default=str)}",
            schema=ReplanningAssessment,
        )
    except Exception as exc:
        raise RuntimeError(f"LLM replanning analysis failed: {exc}") from exc


def replanner_node(state: AgentState, deps: "GraphDependencies") -> AgentState:
    if state.requirements is None or state.previous_requirements is None:
        return state

    changes = _build_changes(state)
    state.changed_constraints = changes
    if not changes:
        state.replanning_notes = []
        state.replanning_tags = []
        return state

    previous_ids, current_ids, dropped_ids = _build_shortlist_delta(state)
    assessment = _analyze_with_llm(state, deps, changes, previous_ids, current_ids, dropped_ids)

    state.replanning_tags = assessment.impact_tags
    state.replanning_notes = assessment.notes
    return state
