from __future__ import annotations

from datetime import date
from typing import TYPE_CHECKING

from src.tools.relocation_db import (
    GetClientProfileInput,
    GetRelocationCaseInput,
    SearchDistrictsInput,
    SupportedGeography,
)

from .llm import require_structured_llm
from .message_understanding import IntakeExtraction
from .state import AgentState, Household, RentalRequirements

if TYPE_CHECKING:
    from .dependencies import GraphDependencies


def _extract_with_llm(
    state: AgentState,
    deps: "GraphDependencies",
    reference_date: date,
    supported_geography: SupportedGeography,
) -> IntakeExtraction:
    llm = require_structured_llm(deps.llm, "Intake extraction")

    case_json = state.relocation_case.model_dump(mode="json") if state.relocation_case else None
    previous_json = state.previous_requirements.model_dump(mode="json") if state.previous_requirements else None
    supported_cities = ", ".join(supported_geography.cities)
    supported_cities_clause = (
        f"Supported cities in the training prototype are: {supported_cities}. "
        if supported_cities
        else ""
    )
    system_prompt = (
        "You extract structured rental requirements for a relocation housing assistant. "
        "Return only fields explicitly stated or clearly implied by the user. "
        "Do not invent values. "
        "For pets return a normalized list like ['cat'] or ['dog', 'dog']. "
        "Use null when the message does not specify a field. "
        f"{supported_cities_clause}"
        "For country use only supported countries when clearly stated. "
        "Use center_preference='prefer_center' when the user explicitly wants central/downtown areas. "
        "Use center_preference='center_not_required' when the user explicitly says the center is not required. "
        "Otherwise use center_preference='unspecified'. "
        "Set office_dependency=true when the user mentions office commute, office location, or travel time to office. "
        "If the user says documents are ready, set document_status=complete. "
        "If the user says documents are still being collected, set document_status=incomplete_docs."
    )
    user_prompt = (
        f"User message:\n{state.user_message}\n\n"
        f"Reference date for relative move-in parsing: {reference_date.isoformat()}\n"
        f"Current relocation case JSON:\n{case_json}\n\n"
        f"Previous requirements JSON:\n{previous_json}\n"
    )
    try:
        return llm.extract_json(system_prompt=system_prompt, user_prompt=user_prompt, schema=IntakeExtraction)
    except Exception as exc:
        raise RuntimeError(f"LLM intake extraction failed: {exc}") from exc


def _requirements_from_context(state: AgentState) -> RentalRequirements:
    if state.previous_requirements is not None:
        return state.previous_requirements.model_copy(deep=True)
    if state.relocation_case is not None:
        case = state.relocation_case
        household = state.client_profile.household if state.client_profile else Household()
        return RentalRequirements(
            city=case.city,
            country=case.country,
            move_in_date=case.move_in_date,
            monthly_budget=case.monthly_budget,
            upfront_budget=case.upfront_budget,
            household=household,
            preferred_districts=case.preferred_districts,
            office_zone=case.office_zone,
            max_commute_minutes=case.max_commute_minutes,
            rooms_min=case.rooms_min,
            furnished=case.furnished,
            school_requirement=case.needs_school_access,
            lease_months=case.lease_months,
            has_passport=state.client_profile.has_passport if state.client_profile else None,
            employer_support=state.client_profile.employer_support if state.client_profile else None,
            citizenship=state.client_profile.citizenship if state.client_profile else None,
            notes=[*case.notes, f"urgency:{case.urgency_level}", f"document_status:{case.document_status}"],
        )
    if state.requirements is not None:
        return state.requirements.model_copy(deep=True)
    return RentalRequirements()


def _load_case_context(state: AgentState, deps: "GraphDependencies") -> None:
    if state.case_id and state.relocation_case is None:
        state.relocation_case = deps.db_tools.get_relocation_case(GetRelocationCaseInput(case_id=state.case_id))
    if state.client_id and state.client_profile is None:
        state.client_profile = deps.db_tools.get_client_profile(GetClientProfileInput(client_id=state.client_id))
    if state.client_profile is None and state.relocation_case is not None:
        state.client_id = state.relocation_case.client_id
        state.client_profile = deps.db_tools.get_client_profile(GetClientProfileInput(client_id=state.client_id))


def _apply_intake_extraction(
    requirements: RentalRequirements,
    extraction: IntakeExtraction,
    city_to_country: dict[str, str],
) -> None:
    if extraction.city:
        requirements.city = extraction.city
        requirements.country = city_to_country.get(extraction.city, requirements.country)
    if extraction.country:
        requirements.country = extraction.country
    if extraction.move_in_date:
        requirements.move_in_date = extraction.move_in_date
    if extraction.monthly_budget is not None:
        requirements.monthly_budget = extraction.monthly_budget
    if extraction.upfront_budget is not None:
        requirements.upfront_budget = extraction.upfront_budget
    if extraction.adults is not None:
        requirements.household.adults = extraction.adults
    if extraction.children is not None:
        requirements.household.children = extraction.children
    if extraction.pets is not None:
        requirements.household.pets = extraction.pets
    if extraction.preferred_districts is not None:
        requirements.preferred_districts = extraction.preferred_districts
    if extraction.office_zone:
        requirements.office_zone = extraction.office_zone
    if extraction.max_commute_minutes is not None:
        requirements.max_commute_minutes = extraction.max_commute_minutes
    if extraction.rooms_min is not None:
        requirements.rooms_min = extraction.rooms_min
    if extraction.housing_type is not None:
        requirements.housing_type = extraction.housing_type
    if extraction.furnished is not None:
        requirements.furnished = extraction.furnished
    if extraction.elevator is not None:
        requirements.elevator = extraction.elevator
    if extraction.floor_max is not None:
        requirements.floor_max = extraction.floor_max
    if extraction.school_requirement is not None:
        requirements.school_requirement = extraction.school_requirement
    if extraction.lease_months is not None:
        requirements.lease_months = extraction.lease_months
    if extraction.has_passport is not None:
        requirements.has_passport = extraction.has_passport
    if extraction.employer_support is not None:
        requirements.employer_support = extraction.employer_support
    if extraction.citizenship is not None:
        requirements.citizenship = extraction.citizenship


def _detect_missing_fields(
    state: AgentState,
    extraction: IntakeExtraction,
    explicit_household: bool,
) -> list[str]:
    requirements = state.requirements or RentalRequirements()
    missing: list[str] = []
    search_like = state.intent in {"search", "replanning", "preference_conflict", "budget_limit", "clarification"}
    if not search_like:
        return missing

    if not requirements.city:
        missing.append("city")
    if not requirements.move_in_date:
        missing.append("move_in_date")
    if requirements.monthly_budget is None:
        missing.append("monthly_budget")
    if not explicit_household and state.relocation_case is None and state.previous_requirements is None:
        missing.append("household_composition")
    if requirements.rooms_min is None and requirements.housing_type is None:
        missing.append("rooms_or_housing_type")
    if extraction.office_dependency and not requirements.office_zone and not requirements.max_commute_minutes:
        missing.append("office_zone_or_commute_target")
    return missing


def intake_node(state: AgentState, deps: "GraphDependencies") -> AgentState:
    _load_case_context(state, deps)
    supported_geography = deps.db_tools.get_supported_geography()

    if state.intent in {"replanning", "budget_limit"} and state.previous_requirements is None and state.relocation_case is not None:
        state.previous_requirements = _requirements_from_context(state).model_copy(deep=True)

    requirements = _requirements_from_context(state)
    reference_date = requirements.move_in_date or (state.relocation_case.move_in_date if state.relocation_case else date.today())
    extraction = _extract_with_llm(state, deps, reference_date=reference_date, supported_geography=supported_geography)

    _apply_intake_extraction(requirements, extraction, supported_geography.city_to_country)

    if extraction.move_in_date and state.relocation_case is not None and extraction.move_in_date > state.relocation_case.move_in_date:
        state.relocation_case.urgency_level = "normal"
        requirements.notes = [note for note in requirements.notes if not note.startswith("urgency:")]
        requirements.notes.append("urgency:normal")

    if extraction.document_status == "complete":
        if state.relocation_case is not None:
            state.relocation_case.document_status = "complete"
        requirements.notes = [note for note in requirements.notes if not note.startswith("document_status:")]
        requirements.notes.append("document_status:complete")
    elif extraction.document_status == "incomplete_docs":
        if state.relocation_case is not None:
            state.relocation_case.document_status = "incomplete_docs"
        requirements.notes = [note for note in requirements.notes if not note.startswith("document_status:")]
        requirements.notes.append("document_status:incomplete_docs")

    if extraction.center_preference == "prefer_center":
        if requirements.city:
            central_districts = deps.db_tools.search_districts(
                SearchDistrictsInput(city=requirements.city, is_central=True)
            ).districts
            if central_districts:
                requirements.preferred_districts = [
                    district.district_id for district in central_districts
                ]
    elif extraction.center_preference == "center_not_required":
        requirements.preferred_districts = []

    state.requirements = requirements
    explicit_household = any(
        value is not None
        for value in [extraction.adults, extraction.children, extraction.pets]
    )
    state.missing_fields = _detect_missing_fields(
        state,
        extraction=extraction,
        explicit_household=explicit_household or state.relocation_case is not None or state.previous_requirements is not None,
    )

    if state.intent in {"search", "replanning", "budget_limit", "preference_conflict"} and state.missing_fields:
        state.intent = "clarification"

    return state
