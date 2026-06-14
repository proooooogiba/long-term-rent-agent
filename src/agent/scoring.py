from __future__ import annotations

from typing import TYPE_CHECKING

from src.tools.calculations import CompareListingsInput

from .state import AgentState

if TYPE_CHECKING:
    from .dependencies import GraphDependencies


def scoring_node(state: AgentState, deps: "GraphDependencies") -> AgentState:
    if state.requirements is None or not state.candidate_listings:
        return state

    state.ranked_listings = deps.calc_tools.compare_listings(
        CompareListingsInput(
            listing_ids=[listing.listing_id for listing in state.candidate_listings],
            requirements=state.requirements,
        )
    ).ranked_listings

    if state.intent == "budget_limit" and len(state.ranked_listings) >= 2:
        first = state.ranked_listings[0]
        second = state.ranked_listings[1]
        first_is_compact = first.listing.property_type == "studio" or "compact_layout" in first.listing.landlord_flags
        second_is_full = second.listing.property_type != "studio" and "compact_layout" not in second.listing.landlord_flags
        if first_is_compact and second_is_full and (first.total_score - second.total_score) <= 0.05:
            state.ranked_listings[0], state.ranked_listings[1] = second, first
    return state
