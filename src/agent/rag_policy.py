from __future__ import annotations

from typing import TYPE_CHECKING

from src.tools.policy_search import PolicySearchInput

from .state import AgentState

if TYPE_CHECKING:
    from .dependencies import GraphDependencies


def rag_policy_node(state: AgentState, deps: "GraphDependencies") -> AgentState:
    query_parts = [state.user_message]
    if state.requirements:
        if state.requirements.city:
            query_parts.append(state.requirements.city)
        if state.requirements.country:
            query_parts.append(state.requirements.country)
        if state.intent:
            query_parts.append(state.intent)
        if state.requirements.household.pet_count:
            query_parts.append("животные депозит pet-friendly")
        if state.requirements.school_requirement:
            query_parts.append("школы район семья")
        if state.requirements.max_commute_minutes is not None:
            query_parts.append("время в пути офис")
    state.retrieved_policy_chunks = deps.policy_tool.search_policy_docs(
        PolicySearchInput(query=" ".join(query_parts), top_k=5)
    ).chunks
    return state
