from __future__ import annotations

from pydantic import BaseModel, Field

from src.agent.state import (
    District,
    Listing,
    RentalRequirements,
    ScoredListing,
    UpfrontCostEstimate,
)
from src.tools.contracts import RelocationToolsProtocol
from src.tools.relocation_db import GetDistrictInfoInput, GetListingInput


class EstimateUpfrontCostInput(BaseModel):
    listing_id: str


class ScoreListingInput(BaseModel):
    listing_id: str
    requirements: RentalRequirements


class CompareListingsInput(BaseModel):
    listing_ids: list[str]
    requirements: RentalRequirements


class CompareListingsOutput(BaseModel):
    ranked_listings: list[ScoredListing] = Field(default_factory=list)


def _clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _recommended_rooms(requirements: RentalRequirements) -> int:
    if requirements.rooms_min is not None:
        return requirements.rooms_min

    household = requirements.household
    if household.children >= 2:
        return 3
    if household.children == 1:
        return 2
    if household.adults >= 2:
        return 1
    return 1


class CalculationTools:
    def __init__(self, db_tools: RelocationToolsProtocol):
        self.db_tools = db_tools

    def estimate_upfront_cost(self, payload: EstimateUpfrontCostInput) -> UpfrontCostEstimate:
        listing = self.db_tools.get_listing(GetListingInput(listing_id=payload.listing_id))
        if listing is None:
            raise ValueError(f"Listing {payload.listing_id} not found")

        first_month = 0.0 if "booking_only_upfront" in listing.landlord_flags else listing.monthly_rent
        deposit = listing.monthly_rent * listing.deposit_months
        agency_fee = listing.agency_fee
        move_in_fee = listing.move_in_fee
        utilities_reserve = 0.0 if listing.short_term_available else listing.utilities_monthly

        notes: list[str] = []
        if listing.deposit_months >= 1.5:
            notes.append("Повышенный депозит увеличивает стартовую нагрузку.")
        if "booking_only_upfront" in listing.landlord_flags:
            notes.append("Для этого временного варианта на входе берётся только бронирование/сервисный платёж.")
        if "full_docs_required" in listing.landlord_flags:
            notes.append("Требуется полный пакет документов перед подписанием.")

        total = round(first_month + deposit + agency_fee + move_in_fee, 2)
        return UpfrontCostEstimate(
            listing_id=listing.listing_id,
            first_month=round(first_month, 2),
            deposit=round(deposit, 2),
            agency_fee=round(agency_fee, 2),
            move_in_fee=round(move_in_fee, 2),
            utilities_reserve=round(utilities_reserve, 2),
            total=total,
            currency=listing.currency,
            notes=notes,
        )

    def score_listing(self, payload: ScoreListingInput) -> ScoredListing:
        listing = self.db_tools.get_listing(GetListingInput(listing_id=payload.listing_id))
        if listing is None:
            raise ValueError(f"Listing {payload.listing_id} not found")
        district = self.db_tools.get_district_info(GetDistrictInfoInput(district_id=listing.district_id))
        return self._score_listing_model(listing, payload.requirements, district)

    def compare_listings(self, payload: CompareListingsInput) -> CompareListingsOutput:
        scored = [
            self.score_listing(
                ScoreListingInput(
                    listing_id=listing_id,
                    requirements=payload.requirements,
                )
            )
            for listing_id in payload.listing_ids
        ]
        scored.sort(key=lambda item: item.total_score, reverse=True)
        return CompareListingsOutput(ranked_listings=scored)

    def _score_listing_model(
        self,
        listing: Listing,
        requirements: RentalRequirements,
        district: District | None,
    ) -> ScoredListing:
        estimate = self.estimate_upfront_cost(EstimateUpfrontCostInput(listing_id=listing.listing_id))
        household = requirements.household
        violations: list[str] = []
        pros: list[str] = []
        cons: list[str] = []

        if requirements.monthly_budget:
            if listing.monthly_rent <= requirements.monthly_budget:
                budget_fit = _clamp(1.0 - (requirements.monthly_budget - listing.monthly_rent) / max(requirements.monthly_budget * 4, 1))
                pros.append("Аренда укладывается в месячный бюджет.")
            else:
                over_ratio = (listing.monthly_rent - requirements.monthly_budget) / requirements.monthly_budget
                budget_fit = _clamp(0.7 - over_ratio * 1.2)
                cons.append("Ежемесячная аренда выше целевого бюджета.")
                violations.append("monthly_budget_exceeded")
        else:
            budget_fit = 0.5

        if requirements.upfront_budget:
            if estimate.total <= requirements.upfront_budget:
                upfront_fit = _clamp(1.0 - (requirements.upfront_budget - estimate.total) / max(requirements.upfront_budget * 4, 1))
                pros.append("Стартовые расходы выглядят подъёмно.")
            else:
                over_ratio = (estimate.total - requirements.upfront_budget) / requirements.upfront_budget
                upfront_fit = _clamp(0.65 - over_ratio * 1.4)
                cons.append("Стартовые расходы выходят за пределы доступного бюджета.")
                violations.append("upfront_budget_exceeded")
        else:
            upfront_fit = 0.55

        required_rooms = _recommended_rooms(requirements)
        occupants = household.total_members + max(household.pet_count - 1, 0)
        room_fit = 1.0 if listing.rooms >= required_rooms else _clamp(0.2 + 0.3 * listing.rooms)
        occupancy_fit = 1.0 if listing.max_occupants >= household.total_members else 0.0
        area_target = max(26.0, household.total_members * 18.0)
        area_fit = _clamp(listing.area_sqm / area_target)
        household_fit = round((room_fit * 0.55) + (occupancy_fit * 0.25) + (area_fit * 0.20), 4)
        if listing.property_type == "studio" or "compact_layout" in listing.landlord_flags:
            household_fit = round(household_fit * (0.72 if household.adults >= 2 or household.children > 0 else 0.65), 4)
            cons.append("Компактный формат может быть менее удобен на дистанции, даже если формально проходит по бюджету.")
        if listing.rooms >= required_rooms:
            pros.append("Количество комнат соответствует составу домохозяйства.")
        else:
            cons.append("Комнат меньше, чем желательно для этого состава домохозяйства.")
            violations.append("rooms_insufficient")
        if listing.max_occupants < household.total_members:
            cons.append("Лимит жильцов у объекта слишком низкий.")
            violations.append("occupancy_limit")

        if household.pet_count == 0:
            pet_fit = 1.0
        elif listing.pet_friendly and (listing.max_pets is None or listing.max_pets >= household.pet_count):
            pet_fit = 1.0 if listing.max_pets is None or listing.max_pets >= household.pet_count else 0.7
            pros.append("Политика по животным совместима с кейсом.")
        else:
            pet_fit = 0.0
            cons.append("Объект не подходит по политике размещения животных.")
            violations.append("pet_policy_mismatch")

        if requirements.move_in_date and listing.available_from > requirements.move_in_date:
            days_late = (listing.available_from - requirements.move_in_date).days
            commute_penalty = 0.0
            availability_penalty = _clamp(0.7 - days_late / 30)
            cons.append("Объект недоступен к нужной дате заселения.")
            violations.append("move_in_unavailable")
        else:
            availability_penalty = 1.0
            commute_penalty = 0.0

        commute_minutes = listing.commute_to_office_minutes or district.commute_to_center_minutes if district else None
        if requirements.max_commute_minutes and commute_minutes is not None:
            if commute_minutes <= requirements.max_commute_minutes:
                commute_fit = _clamp(1.0 - commute_minutes / max(requirements.max_commute_minutes * 5, 1))
                pros.append("Время в пути укладывается в заданный предел.")
            else:
                over = commute_minutes - requirements.max_commute_minutes
                commute_fit = _clamp(0.7 - over / max(requirements.max_commute_minutes, 1))
                cons.append("Время в пути хуже желаемого коридора.")
                if over > 10 or requirements.max_commute_minutes <= 30:
                    violations.append("commute_too_long")
        else:
            commute_fit = 0.65 if commute_minutes is None else _clamp(1.0 - commute_minutes / 120)
        commute_fit = max(0.0, commute_fit - commute_penalty)
        commute_fit *= availability_penalty

        district_fit = 0.55
        if district:
            signals: list[float] = [district.safety_score, district.transit_score]
            if requirements.school_requirement or household.children > 0:
                signals.append(district.school_score)
            if requirements.preferred_districts:
                if district.district_id in requirements.preferred_districts or district.name in requirements.preferred_districts:
                    signals.append(1.0)
                    pros.append("Район совпадает с предпочтениями.")
                else:
                    signals.append(0.35)
            if household.children > 0 and district.family_friendly:
                pros.append("Район хорошо подходит семейному сценарию.")
            if household.children > 0 and not district.family_friendly:
                cons.append("Район слабее по семейной инфраструктуре.")
            district_fit = sum(signals) / len(signals)

        total_score = (
            budget_fit * 0.25
            + commute_fit * 0.20
            + household_fit * 0.20
            + district_fit * 0.15
            + pet_fit * 0.10
            + upfront_fit * 0.10
        )

        if listing.short_term_available and (requirements.lease_months or 12) >= 6 and "urgency:urgent" not in requirements.notes:
            total_score *= 0.72
            cons.append("Это временное жильё, а не оптимальный долгосрочный договор.")
        if "full_docs_required" in listing.landlord_flags:
            total_score *= 0.93
        if listing.income_verification_required:
            total_score *= 0.95

        if listing.deposit_months >= 1.5:
            cons.append("Повышенный депозит увеличивает риск по входу в аренду.")
        if listing.furnished:
            pros.append("Квартира меблирована.")
        elif requirements.furnished:
            cons.append("Нет мебели, хотя она была предпочтительна.")

        if listing.income_verification_required:
            cons.append("Арендодатель требует проверку дохода или документов.")
        if listing.property_type == "temporary_housing":
            pros.append("Подходит как безопасный мостик для срочного переезда.")

        return ScoredListing(
            listing=listing,
            total_score=round(total_score, 4),
            sub_scores={
                "budget_fit": round(budget_fit, 4),
                "commute_fit": round(commute_fit, 4),
                "household_fit": round(household_fit, 4),
                "district_fit": round(district_fit, 4),
                "pet_policy_fit": round(pet_fit, 4),
                "upfront_cost_fit": round(upfront_fit, 4),
            },
            pros=pros,
            cons=cons,
            constraint_violations=sorted(set(violations)),
            estimated_upfront_cost=estimate,
        )
