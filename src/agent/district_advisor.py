from __future__ import annotations

from typing import TYPE_CHECKING

from src.tools.relocation_db import (
    GetCityInfoInput,
    GetCountryProfileInput,
    GetDistrictInfoInput,
    SearchServicesInput,
)

from .state import AgentState, DistrictRecommendation

if TYPE_CHECKING:
    from .dependencies import GraphDependencies


def district_advisor_node(state: AgentState, deps: "GraphDependencies") -> AgentState:
    if state.requirements and state.requirements.city:
        state.city_info = deps.db_tools.get_city_info(GetCityInfoInput(city=state.requirements.city))

    country_name = None
    if state.requirements and state.requirements.country:
        country_name = state.requirements.country
    elif state.city_info:
        country_name = state.city_info.country

    if country_name:
        state.country_profile = deps.db_tools.get_country_profile(GetCountryProfileInput(country=country_name))

    if state.candidate_listings:
        seen: set[str] = set()
        recommendations: list[DistrictRecommendation] = []
        for listing in state.candidate_listings:
            if listing.district_id in seen:
                continue
            seen.add(listing.district_id)
            district = deps.db_tools.get_district_info(GetDistrictInfoInput(district_id=listing.district_id))
            if district is None:
                continue

            tradeoffs: list[str] = []
            rationale = (
                "Район даёт сильный баланс по ежедневной инфраструктуре."
                if district.family_friendly
                else "Район выигрывает у более дорогих альтернатив по логистике или цене."
            )
            if state.requirements and state.requirements.max_commute_minutes and listing.commute_to_office_minutes:
                if listing.commute_to_office_minutes > state.requirements.max_commute_minutes:
                    tradeoffs.append("Придётся принять более длинную дорогу до офиса.")
            if state.requirements and state.requirements.school_requirement and not district.family_friendly:
                tradeoffs.append("Семейная инфраструктура слабее, чем у лучших семейных районов.")

            recommendations.append(
                DistrictRecommendation(
                    district_id=district.district_id,
                    city=district.city,
                    rationale=rationale,
                    estimated_rent_range=f"{int(district.avg_rent_from)}-{int(district.avg_rent_to)} USD",
                    estimated_commute_minutes=listing.commute_to_office_minutes or district.commute_to_center_minutes,
                    tradeoffs=tradeoffs,
                )
            )
            if len(recommendations) >= 3:
                break
        state.district_recommendations = recommendations

    service_tags: list[str] = []
    if state.relocation_case and state.relocation_case.urgency_level == "urgent":
        service_tags.append("urgent_move")
    if state.relocation_case and state.relocation_case.document_status != "complete":
        service_tags.append("incomplete_docs")
    if state.requirements and state.requirements.household.pet_count > 0:
        service_tags.append("pet_owner")
    if state.requirements and ((state.requirements.school_requirement is True) or state.requirements.household.children > 0):
        service_tags.extend(["family", "school_required"])
    if state.requirements and state.requirements.has_passport is False:
        service_tags.append("passport_issue")

    services = deps.db_tools.search_relocation_services(
        SearchServicesInput(
            city=state.requirements.city if state.requirements else None,
            country=country_name,
            tags=service_tags,
        )
    ).services
    state.relocation_services = services[:3]
    return state
