from __future__ import annotations

from typing import TYPE_CHECKING

from .llm import require_structured_llm
from .message_understanding import RouterDecision
from .state import AgentState

if TYPE_CHECKING:
    from .dependencies import GraphDependencies


def _route_with_llm(state: AgentState, deps: "GraphDependencies") -> AgentState:
    llm = require_structured_llm(deps.llm, "Routing")

    previous_requirements = state.previous_requirements.model_dump(mode="json") if state.previous_requirements else None
    system_prompt = (
        "You are a router for a relocation and rental assistant. "
        "Classify the user's message into exactly one intent. "
        "Use 'info' for questions about deposits, contracts, districts, registration, documents, or rules. "
        "Use 'search' for requests to find housing. "
        "Use 'replanning' when the user changes budget, move-in date, city, district, family composition, or pet status. "
        "Use 'budget_limit' when the main change or issue is budget pressure. "
        "Use 'preference_conflict' when user asks for a combination that likely conflicts with budget/commute/family/pet needs. "
        "Use 'clarification' when critical data is missing for search. "
        "Use 'escalation' for risky legal/financial/document questions or requests for certainty."
    )
    user_prompt = (
        f"User message:\n{state.user_message}\n\n"
        f"Has previous requirements: {bool(state.previous_requirements)}\n"
        f"Case id present: {bool(state.case_id)}\n"
        f"Previous requirements JSON:\n{previous_requirements}\n"
    )

    try:
        decision = llm.extract_json(system_prompt=system_prompt, user_prompt=user_prompt, schema=RouterDecision)
        state.intent = decision.intent
        return state
    except Exception as exc:
        raise RuntimeError(f"LLM routing failed: {exc}") from exc


def router_node(state: AgentState, deps: "GraphDependencies") -> AgentState:
    return _route_with_llm(state, deps)
