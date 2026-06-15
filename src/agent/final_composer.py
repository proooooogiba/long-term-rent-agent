from __future__ import annotations

import json
import re
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

from .llm import require_structured_llm
from .llm import should_use_demo_fallback
from .state import AgentState, FinalRecommendation, ScoredListing

if TYPE_CHECKING:
    from .dependencies import GraphDependencies


def _demo_llm():
    from .demo_llm import DemoStructuredLLM

    return DemoStructuredLLM()


URL_RE = re.compile(r"https?://[^\s]+")


class InfoAnswerSections(BaseModel):
    summary: str
    details: list[str] = Field(default_factory=list)
    case_impact: list[str] = Field(default_factory=list)


class ClarificationAnswerSections(BaseModel):
    preface: str
    questions: list[str] = Field(default_factory=list)


class EscalationAnswerSections(BaseModel):
    reason_summary: str
    reasons: list[str] = Field(default_factory=list)
    preparations: list[str] = Field(default_factory=list)


class RecommendationAnswerSections(BaseModel):
    summary: str
    important_notes: list[str] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    clarification_lines: list[str] = Field(default_factory=list)


def _listing_url(scored: ScoredListing) -> str | None:
    for note in scored.listing.notes:
        if note.startswith("url:"):
            url = note.split("url:", 1)[1].strip()
            return url or None
    return None


def _listing_link_label(scored: ScoredListing) -> str:
    listing = scored.listing
    label = listing.district_name.strip() if listing.district_name and listing.district_name != "Район не указан" else listing.title.strip()
    if listing.city and listing.city not in label:
        label = f"{label}, {listing.city}"
    return label.replace("[", "\\[").replace("]", "\\]")


def _listing_reference(scored: ScoredListing) -> str:
    url = _listing_url(scored)
    if not url:
        return f"`{scored.listing.listing_id}`"
    return f"[{_listing_link_label(scored)}]({url})"


def _format_listing_block(rank: int, scored: ScoredListing) -> str:
    listing = scored.listing
    why = "; ".join(scored.pros[:2]) or "Подходит по базовому набору ограничений."
    risks = "; ".join(scored.cons[:2]) or "Критичных компромиссов не видно."
    return (
        f"{rank}. {listing.title} {_listing_reference(scored)} — {listing.monthly_rent:.0f} {listing.currency}/мес, "
        f"{listing.district_name}, доступно с {listing.available_from.isoformat()}\n"
        f"   Почему подходит: {why}\n"
        f"   Риски/компромиссы: {risks}\n"
        f"   Стартовые расходы: {scored.estimated_upfront_cost.total:.0f} {scored.estimated_upfront_cost.currency}\n"
        f"   Score: {scored.total_score:.3f}"
    )


def _serialize_listing(scored: ScoredListing) -> dict[str, Any]:
    listing = scored.listing
    return {
        "listing_id": listing.listing_id,
        "title": listing.title,
        "city": listing.city,
        "district_name": listing.district_name,
        "monthly_rent": listing.monthly_rent,
        "currency": listing.currency,
        "available_from": listing.available_from.isoformat(),
        "rooms": listing.rooms,
        "area_sqm": listing.area_sqm,
        "pet_friendly": listing.pet_friendly,
        "commute_to_office_minutes": listing.commute_to_office_minutes,
        "total_score": scored.total_score,
        "sub_scores": scored.sub_scores,
        "pros": scored.pros,
        "cons": scored.cons,
        "constraint_violations": scored.constraint_violations,
        "estimated_upfront_cost": {
            "total": scored.estimated_upfront_cost.total,
            "currency": scored.estimated_upfront_cost.currency,
            "notes": scored.estimated_upfront_cost.notes,
        },
    }


def _serialize_state_context(state: AgentState, top_k: int = 5) -> dict[str, Any]:
    return {
        "user_message": state.user_message,
        "intent": state.intent,
        "requirements": state.requirements.model_dump(mode="json") if state.requirements else None,
        "city_info": state.city_info.model_dump(mode="json") if state.city_info else None,
        "country_profile": state.country_profile.model_dump(mode="json") if state.country_profile else None,
        "verification_result": state.verification_result.model_dump(mode="json") if state.verification_result else None,
        "replanning_notes": state.replanning_notes,
        "replanning_tags": state.replanning_tags,
        "warnings": state.warnings,
        "missing_fields": state.missing_fields,
        "district_recommendations": [item.model_dump(mode="json") for item in state.district_recommendations[:3]],
        "relocation_services": [item.model_dump(mode="json") for item in state.relocation_services[:3]],
        "retrieved_policy_chunks": [item.model_dump(mode="json") for item in state.retrieved_policy_chunks[:top_k]],
        "ranked_listings": [_serialize_listing(item) for item in state.ranked_listings[:top_k]],
    }


def _collect_reference_links(state: AgentState, limit: int = 8) -> list[str]:
    collected: list[str] = []
    seen: set[str] = set()

    def add_urls(text: str | None) -> None:
        if not text:
            return
        for raw_url in URL_RE.findall(text):
            url = raw_url.rstrip(").,]")
            if url and url not in seen:
                seen.add(url)
                collected.append(url)
                if len(collected) >= limit:
                    return

    if state.country_profile:
        for note in state.country_profile.notes:
            add_urls(note)
            if len(collected) >= limit:
                return collected

    for chunk in state.retrieved_policy_chunks[:5]:
        add_urls(chunk.text)
        if len(collected) >= limit:
            break

    return collected


def _call_llm_or_raise(
    state: AgentState,
    deps: "GraphDependencies",
    system_prompt: str,
    schema: type[BaseModel],
) -> BaseModel | None:
    if deps.llm is None:
        return None

    payload = json.dumps(_serialize_state_context(state), ensure_ascii=False, indent=2)
    try:
        return deps.llm.extract_json(
            system_prompt=system_prompt,
            user_prompt=f"Context JSON:\n{payload}",
            schema=schema,
        )
    except Exception as exc:
        if not should_use_demo_fallback(exc, getattr(deps, "llm_mode", "auto")):
            raise RuntimeError(f"LLM final composition failed: {exc}") from exc
        state.warnings.append(f"LLM final composition fallback: {exc}")
        return _demo_llm().extract_json(
            system_prompt=system_prompt,
            user_prompt=f"Context JSON:\n{payload}",
            schema=schema,
        )


def _fallback_info_sections(state: AgentState) -> InfoAnswerSections:
    details = []
    for chunk in state.retrieved_policy_chunks[:3]:
        text = chunk.text.strip().replace("\n", " ")
        if text:
            details.append(text[:220])
    case_impact = []
    if state.city_info:
        case_impact.append(state.city_info.commute_guidance)
    if state.country_profile:
        case_impact.append(f"Страна кейса: {state.country_profile.name}. Нужна отдельная проверка актуальных правил въезда и регистрации.")
    if not case_impact:
        case_impact.append("Для точного ответа лучше зафиксировать город, бюджет и состав домохозяйства.")
    return InfoAnswerSections(
        summary="Подобрал справочный ответ по правилам аренды и релокации из базы знаний проекта.",
        details=details or ["Смотрю на сочетание правил аренды, платежей, районов и базовых relocation-ограничений."],
        case_impact=case_impact,
    )


def _fallback_escalation_sections(state: AgentState) -> EscalationAnswerSections:
    reasons = state.verification_result.failed_checks if state.verification_result else []
    preparations = [
        f"{service.name}: {service.description} ({service.cost:.0f} {service.currency})"
        for service in state.relocation_services[:2]
    ]
    if not preparations:
        preparations = ["Подготовить паспортный маршрут, документы и подтверждение дохода."]
    return EscalationAnswerSections(
        reason_summary="Кейс требует отдельной человеческой проверки.",
        reasons=reasons or ["Есть юридические, документные или финансовые риски, которые нельзя подтверждать автоматически."],
        preparations=preparations,
    )


def _fallback_recommendation_sections(state: AgentState) -> RecommendationAnswerSections:
    ranked = state.ranked_listings[:3]
    summary_parts = []
    if ranked:
        best = ranked[0]
        summary_parts.append(
            f"Лучший текущий вариант — {_listing_reference(best)}: {best.listing.monthly_rent:.0f} {best.listing.currency}/мес, район {best.listing.district_name}."
        )
    if state.replanning_notes:
        summary_parts.append(" ".join(state.replanning_notes))
    if state.verification_result and state.verification_result.warnings:
        summary_parts.append("Есть оговорки по части вариантов, я вынес их отдельно.")

    important_notes = []
    if state.verification_result and state.verification_result.warnings:
        important_notes.extend(state.verification_result.warnings[:4])
    if state.district_recommendations:
        important_notes.extend(
            f"{item.district_id}: {item.rationale} Диапазон аренды {item.estimated_rent_range}."
            for item in state.district_recommendations[:2]
        )

    alternatives = []
    if len(state.ranked_listings) > 3:
        alternatives = [
            f"{_listing_reference(item)}: {item.listing.monthly_rent:.0f} {item.listing.currency}/мес, {item.listing.district_name}"
            for item in state.ranked_listings[3:5]
        ]

    clarification_lines = []
    if state.verification_result and state.verification_result.required_user_clarifications:
        clarification_lines = state.verification_result.required_user_clarifications

    return RecommendationAnswerSections(
        summary=" ".join(summary_parts) or "Подбор выполнен.",
        important_notes=important_notes,
        alternatives=alternatives,
        clarification_lines=clarification_lines,
    )


def _compose_info_answer(state: AgentState, deps: "GraphDependencies") -> InfoAnswerSections:
    system_prompt = (
        "You are the final response composer for a relocation and rental assistant. "
        "Use only the provided context. "
        "Write in Russian. "
        "Answer informational questions with three sections: summary, details, case impact. "
        "Be explicit about uncertainty and do not provide legal guarantees. "
        "Return concise JSON only."
    )
    response = _call_llm_or_raise(state, deps, system_prompt, InfoAnswerSections)
    return response if isinstance(response, InfoAnswerSections) else _fallback_info_sections(state)


def _compose_clarification_answer(state: AgentState, deps: "GraphDependencies") -> ClarificationAnswerSections:
    system_prompt = (
        "You are the final response composer for a relocation and rental assistant. "
        "Use the provided missing fields and verification clarifications to formulate short user-facing clarification questions in Russian. "
        "Do not invent new missing requirements beyond the context. "
        "Return concise JSON only."
    )
    payload = json.dumps(_serialize_state_context(state), ensure_ascii=False, indent=2)
    try:
        llm = require_structured_llm(deps.llm, "Clarification answer composition")
        return llm.extract_json(
            system_prompt=system_prompt,
            user_prompt=f"Context JSON:\n{payload}",
            schema=ClarificationAnswerSections,
        )
    except Exception as exc:
        if should_use_demo_fallback(exc, getattr(deps, "llm_mode", "auto")):
            state.warnings.append(f"LLM clarification fallback: {exc}")
            return _demo_llm().extract_json(
                system_prompt=system_prompt,
                user_prompt=f"Context JSON:\n{payload}",
                schema=ClarificationAnswerSections,
            )
        raise RuntimeError(f"LLM clarification composition failed: {exc}") from exc


def _compose_escalation_answer(state: AgentState, deps: "GraphDependencies") -> EscalationAnswerSections:
    system_prompt = (
        "You are the final response composer for a relocation and rental assistant. "
        "Explain in Russian why the case should be handed to a human, using only the provided failed checks, warnings, policy context, and relocation services. "
        "Do not overstate certainty. "
        "Return concise JSON only."
    )
    response = _call_llm_or_raise(state, deps, system_prompt, EscalationAnswerSections)
    return response if isinstance(response, EscalationAnswerSections) else _fallback_escalation_sections(state)


def _compose_recommendation_answer(state: AgentState, deps: "GraphDependencies") -> RecommendationAnswerSections:
    system_prompt = (
        "You are the final response composer for a relocation and rental assistant. "
        "Use only the ranked listings, verification result, district recommendations, policy context, and replanning notes provided in the context. "
        "Write in Russian. "
        "Do not invent listing facts or prices. "
        "Summarize the shortlist, note important trade-offs, mention alternatives, and mention if any clarification is still useful. "
        "Return concise JSON only."
    )
    response = _call_llm_or_raise(state, deps, system_prompt, RecommendationAnswerSections)
    return response if isinstance(response, RecommendationAnswerSections) else _fallback_recommendation_sections(state)


def final_composer_node(state: AgentState, deps: "GraphDependencies") -> AgentState:
    verification = state.verification_result

    if state.intent == "info":
        sections = _compose_info_answer(state, deps)
        details_text = "\n".join(f"- {item}" for item in sections.details) or "- Нужна дополнительная проверка по документам и условиям аренды."
        impact_text = "\n".join(f"- {item}" for item in sections.case_impact) or "- Для точного кейса лучше уточнить город, бюджет и сроки."
        source_links = _collect_reference_links(state)
        sources_text = ""
        if source_links:
            sources_text = "\n\nИсточники:\n" + "\n".join(f"- {item}" for item in source_links)
        state.final_answer = (
            "Краткий ответ:\n"
            f"{sections.summary}\n\n"
            "Подробности:\n"
            f"{details_text}\n\n"
            "Что это значит для вашего кейса:\n"
            f"{impact_text}"
            f"{sources_text}"
        )
        state.final_recommendation = FinalRecommendation(summary=sections.summary)
        return state

    if verification and verification.status == "clarification":
        sections = _compose_clarification_answer(state, deps)
        numbered = "\n".join(f"{idx}. {question}" for idx, question in enumerate(sections.questions, start=1))
        state.final_answer = f"{sections.preface}\n{numbered}"
        state.final_recommendation = FinalRecommendation(
            summary="Нужно уточнение перед подбором.",
            clarifying_questions=sections.questions,
        )
        return state

    if verification and verification.status == "escalation":
        sections = _compose_escalation_answer(state, deps)
        reasons = "\n".join(f"- {item}" for item in sections.reasons)
        preparations = "\n".join(f"- {item}" for item in sections.preparations)
        state.final_answer = (
            "Этот кейс лучше передать человеку, потому что:\n"
            f"{reasons or '- Нужна отдельная человеческая проверка.'}\n\n"
            "Что можно подготовить заранее:\n"
            f"{preparations or '- Подготовить документы, паспортный маршрут и подтверждение дохода.'}"
        )
        state.final_recommendation = FinalRecommendation(
            summary=sections.reason_summary,
            escalation_reason="; ".join(sections.reasons) if sections.reasons else sections.reason_summary,
        )
        return state

    ranked = state.ranked_listings[:3]
    sections = _compose_recommendation_answer(state, deps)
    top_blocks = "\n\n".join(_format_listing_block(idx, scored) for idx, scored in enumerate(ranked, start=1))
    important_notes = "\n".join(f"- {item}" for item in sections.important_notes) or "- Существенных дополнительных оговорок нет."
    alternatives = "\n".join(f"- {item}" for item in sections.alternatives) or "- Основной shortlist уже покрывает разумные компромиссы."
    clarification_lines = "\n".join(f"- {item}" for item in sections.clarification_lines) or "- На текущем наборе вводных можно продолжать поиск без новых уточнений."

    state.final_answer = (
        "Краткий вывод:\n"
        f"{sections.summary}\n\n"
        "Топ-3 варианта:\n"
        f"{top_blocks}\n\n"
        "Что важно учесть:\n"
        f"{important_notes}\n\n"
        "Альтернативы:\n"
        f"{alternatives}\n\n"
        "Нужны уточнения:\n"
        f"{clarification_lines}"
    )
    state.final_recommendation = FinalRecommendation(
        summary=sections.summary,
        top_choices=ranked,
        alternatives=sections.alternatives,
        important_notes=sections.important_notes,
        clarifying_questions=sections.clarification_lines,
    )
    return state
