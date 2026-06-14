from __future__ import annotations

from typing import TYPE_CHECKING

from src.tools.relocation_db import SearchServicesInput

from .state import AgentState, VerificationResult

if TYPE_CHECKING:
    from .dependencies import GraphDependencies


CRITICAL_VIOLATIONS = {
    "monthly_budget_exceeded",
    "pet_policy_mismatch",
    "rooms_insufficient",
    "occupancy_limit",
    "move_in_unavailable",
    "commute_too_long",
}


def verifier_node(state: AgentState, deps: "GraphDependencies") -> AgentState:
    if state.intent == "escalation":
        state.verification_result = VerificationResult(
            status="escalation",
            failed_checks=["requires_human_or_legal_review"],
            warnings=["Запрос выходит за рамки безопасной учебной автоматизации."],
            required_user_clarifications=["подготовить документы и проверить актуальные официальные правила"],
        )
        return state

    if state.missing_fields:
        state.verification_result = VerificationResult(
            status="clarification",
            failed_checks=["missing_required_fields"],
            required_user_clarifications=state.missing_fields,
        )
        return state

    if state.intent == "info":
        state.verification_result = VerificationResult(status="approved")
        return state

    if state.country_profile and state.requirements and state.requirements.has_passport is False:
        if not state.country_profile.relocation_by_internal_passport:
            state.relocation_services = deps.db_tools.search_relocation_services(
                SearchServicesInput(
                    city=state.requirements.city,
                    country=state.requirements.country,
                    tags=["passport_issue", "escalation"],
                )
            ).services[:3]
            state.verification_result = VerificationResult(
                status="escalation",
                failed_checks=["document_status_requires_human_review"],
                warnings=[
                    "Страна назначения в учебном профиле требует загранпаспорт или отдельную документную проверку.",
                ],
                required_user_clarifications=["подтвердить документный маршрут и легальный способ въезда"],
            )
            state.intent = "escalation"
            return state

    if not state.ranked_listings:
        state.verification_result = VerificationResult(
            status="clarification",
            failed_checks=["no_candidate_listings"],
            required_user_clarifications=["уточнить город, бюджет или критерии, которые можно ослабить"],
        )
        return state

    compliant = []
    blocked = []
    warnings: list[str] = []

    for scored in state.ranked_listings:
        violations = set(scored.constraint_violations)
        if state.relocation_case and state.relocation_case.document_status != "complete" and "full_docs_required" in scored.listing.landlord_flags:
            violations.add("full_docs_required")
            scored.constraint_violations.append("full_docs_required")
        if scored.listing.deposit_months >= 1.5:
            warnings.append(f"{scored.listing.listing_id}: повышенный депозит.")
        if scored.listing.income_verification_required:
            warnings.append(f"{scored.listing.listing_id}: потребуется проверка дохода или документов.")
        if state.client_profile:
            rent_share = scored.listing.monthly_rent / state.client_profile.monthly_income
            if rent_share > 0.45:
                warnings.append(
                    f"{scored.listing.listing_id}: аренда превышает 45% подтверждённого дохода, возможен отказ арендодателя."
                )
        if CRITICAL_VIOLATIONS.intersection(violations) or "full_docs_required" in violations:
            blocked.append(scored)
        else:
            compliant.append(scored)

    state.ranked_listings = compliant + blocked

    if compliant:
        if blocked:
            warnings.append("Часть объектов сохранена только как компромиссные альтернативы с оговорками.")
        state.verification_result = VerificationResult(
            status="approved",
            passed_checks=["basic_constraints_checked", "ranked_listings_available"],
            warnings=sorted(set(warnings)),
        )
        return state

    clarification_questions = ["что можно ослабить в первую очередь: бюджет, район, время в пути или формат жилья"]
    if state.intent in {"preference_conflict", "budget_limit"}:
        clarification_questions = [
            "какое ограничение можно ослабить: бюджет, центр, время в пути или pet-friendly требование",
        ]

    state.verification_result = VerificationResult(
        status="clarification",
        failed_checks=sorted(set(item for scored in blocked for item in scored.constraint_violations)),
        warnings=sorted(set(warnings)),
        required_user_clarifications=clarification_questions,
    )
    return state
