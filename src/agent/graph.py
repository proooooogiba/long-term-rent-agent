from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable

from .dependencies import GraphDependencies
from .district_advisor import district_advisor_node
from .final_composer import final_composer_node
from .intake import intake_node
from .listing_search import listing_search_node
from .rag_policy import rag_policy_node
from .replanner import replanner_node
from .router import router_node
from .scoring import scoring_node
from .state import AgentState, ScoredListing
from .verifier import verifier_node


@dataclass
class AgentTraceStep:
    node: str
    title: str
    summary: str
    duration_ms: float


AgentTraceCallback = Callable[[str], None]


def _format_top_listing(scored: ScoredListing | None) -> str:
    if scored is None:
        return "нет подходящего варианта"
    listing = scored.listing
    return (
        f"{listing.listing_id} ({listing.monthly_rent:.0f} {listing.currency}/мес, "
        f"{listing.district_name})"
    )


def _summarize_trace_step(node_name: str, state: AgentState) -> str:
    if node_name == "router":
        return f"Определён intent: {state.intent or 'не определён'}."

    if node_name == "intake":
        requirements = state.requirements
        if requirements is None:
            return "Требования пока не извлечены."

        household_parts = [f"{requirements.household.adults} взр."]
        if requirements.household.children:
            household_parts.append(f"{requirements.household.children} дет.")
        if requirements.household.pets:
            household_parts.append(f"pets: {', '.join(requirements.household.pets)}")

        parts = []
        if requirements.city:
            parts.append(requirements.city)
        if requirements.monthly_budget is not None:
            parts.append(f"бюджет до {requirements.monthly_budget:.0f} {requirements.budget_currency}")
        if requirements.move_in_date:
            parts.append(f"переезд {requirements.move_in_date.isoformat()}")
        parts.append(f"домохозяйство: {', '.join(household_parts)}")
        if state.missing_fields:
            parts.append(f"нужно уточнить: {', '.join(state.missing_fields)}")
        return "; ".join(parts) + "."

    if node_name == "rag_policy":
        chunks = state.retrieved_policy_chunks
        if not chunks:
            return "Релевантные policy-правила не понадобились или не найдены."
        top = ", ".join(chunk.heading for chunk in chunks[:2] if chunk.heading)
        return f"Подтянуто {len(chunks)} policy-чанков. {top or 'Есть контекст по правилам.'}"

    if node_name == "district_advisor":
        return (
            f"Рекомендаций по районам: {len(state.district_recommendations)}; "
            f"сервисов релокации: {len(state.relocation_services)}."
        )

    if node_name == "listing_search":
        warning_note = f" Предупреждений: {len(state.warnings)}." if state.warnings else ""
        return f"Найдено кандидатов: {len(state.candidate_listings)}.{warning_note}"

    if node_name == "scoring":
        top = state.ranked_listings[0] if state.ranked_listings else None
        return (
            f"Отранжировано {len(state.ranked_listings)} вариантов; "
            f"топ: {_format_top_listing(top)}."
        )

    if node_name == "verifier":
        result = state.verification_result
        if result is None:
            return "Верификация не вернула статус."
        return (
            f"Статус: {result.status}; "
            f"warnings={len(result.warnings)}; "
            f"failed_checks={len(result.failed_checks)}."
        )

    if node_name == "replanner":
        if not state.changed_constraints:
            return "Изменений требований относительно предыдущего шага нет."
        changed = ", ".join(state.changed_constraints.keys())
        tags = f" Теги: {', '.join(state.replanning_tags)}." if state.replanning_tags else ""
        return f"Обновлены ограничения: {changed}.{tags}"

    if node_name == "final_composer":
        final_len = len(state.final_answer or "")
        top_choices = len(state.final_recommendation.top_choices) if state.final_recommendation else 0
        return f"Собран финальный ответ ({final_len} символов), top choices: {top_choices}."

    return "Шаг выполнен."


@dataclass
class AgentGraph:
    deps: GraphDependencies = field(default_factory=GraphDependencies)

    def run(
        self,
        state: AgentState,
        trace_steps: list[AgentTraceStep] | None = None,
        trace_callback: AgentTraceCallback | None = None,
    ) -> AgentState:
        graph_nodes = [
            ("router", "Router", router_node),
            ("intake", "Intake", intake_node),
            ("rag_policy", "RAG Policy", rag_policy_node),
            ("district_advisor", "District Advisor", district_advisor_node),
            ("listing_search", "Listing Search", listing_search_node),
            ("scoring", "Scoring", scoring_node),
            ("verifier", "Verifier", verifier_node),
            ("replanner", "Replanner", replanner_node),
            ("final_composer", "Final Composer", final_composer_node),
        ]

        for node_name, title, node_fn in graph_nodes:
            if trace_callback is not None:
                trace_callback(f"{title}: выполняется...")

            started_at = perf_counter()
            state = node_fn(state, self.deps)
            duration_ms = round((perf_counter() - started_at) * 1000, 1)
            step = AgentTraceStep(
                node=node_name,
                title=title,
                summary=_summarize_trace_step(node_name, state),
                duration_ms=duration_ms,
            )

            if trace_steps is not None:
                trace_steps.append(step)
            if trace_callback is not None:
                trace_callback(f"{title}: {step.summary}")
        return state


@dataclass
class RelocationAgent:
    graph: AgentGraph = field(default_factory=AgentGraph)

    def run(
        self,
        user_message: str,
        previous_state: AgentState | None = None,
        client_id: str | None = None,
        case_id: str | None = None,
        trace_steps: list[AgentTraceStep] | None = None,
        trace_callback: AgentTraceCallback | None = None,
    ) -> AgentState:
        persisted_snapshot = None
        same_case = previous_state is not None and (case_id is None or previous_state.case_id == case_id)
        if not same_case and previous_state is None and case_id and self.graph.deps.memory_store is not None:
            persisted_snapshot = self.graph.deps.memory_store.load_case_memory(case_id)
        state = AgentState(
            user_message=user_message,
            client_id=client_id or (previous_state.client_id if previous_state and same_case else None),
            case_id=case_id or (previous_state.case_id if previous_state and same_case else None),
            client_profile=previous_state.client_profile if previous_state and same_case else None,
            relocation_case=previous_state.relocation_case if previous_state and same_case else None,
            previous_requirements=previous_state.requirements.model_copy(deep=True)
            if previous_state and same_case and previous_state.requirements
            else (
                persisted_snapshot.requirements.model_copy(deep=True)
                if persisted_snapshot and persisted_snapshot.requirements
                else None
            ),
            previous_ranked_listings=previous_state.ranked_listings[:] if previous_state and same_case else [],
            persistent_memory_loaded=bool(persisted_snapshot),
            persistent_memory_updated_at=persisted_snapshot.updated_at if persisted_snapshot else None,
            persistent_memory_summary=persisted_snapshot.final_summary if persisted_snapshot else None,
        )
        if not state.previous_ranked_listings and persisted_snapshot:
            state.previous_ranked_listings = [item.model_copy(deep=True) for item in persisted_snapshot.ranked_listings]
        state = self.graph.run(
            state,
            trace_steps=trace_steps,
            trace_callback=trace_callback,
        )
        if self.graph.deps.memory_store is not None:
            self.graph.deps.memory_store.save_state(state)
        return state


@dataclass
class AgentSession:
    agent: RelocationAgent = field(default_factory=RelocationAgent)
    last_state: AgentState | None = None
    last_trace: list[AgentTraceStep] = field(default_factory=list)

    def handle_message(
        self,
        user_message: str,
        client_id: str | None = None,
        case_id: str | None = None,
        trace_callback: AgentTraceCallback | None = None,
    ) -> AgentState:
        trace_steps: list[AgentTraceStep] = []
        self.last_state = self.agent.run(
            user_message=user_message,
            previous_state=self.last_state,
            client_id=client_id,
            case_id=case_id,
            trace_steps=trace_steps,
            trace_callback=trace_callback,
        )
        self.last_trace = trace_steps
        return self.last_state
