from __future__ import annotations

from datetime import date
from typing import Any, Literal

from pydantic import BaseModel, Field


class PolicyChunk(BaseModel):
    source: str
    heading: str
    text: str
    score: float | None = None


class Household(BaseModel):
    adults: int = 1
    children: int = 0
    pets: list[str] = Field(default_factory=list)

    @property
    def pet_count(self) -> int:
        return len(self.pets)

    @property
    def total_members(self) -> int:
        return self.adults + self.children


class RentalRequirements(BaseModel):
    city: str | None = None
    country: str | None = None
    move_in_date: date | None = None
    monthly_budget: float | None = None
    upfront_budget: float | None = None
    budget_currency: str = "USD"
    household: Household = Field(default_factory=Household)
    preferred_districts: list[str] = Field(default_factory=list)
    office_zone: str | None = None
    max_commute_minutes: int | None = None
    rooms_min: int | None = None
    housing_type: str | None = None
    furnished: bool | None = None
    elevator: bool | None = None
    floor_min: int | None = None
    floor_max: int | None = None
    school_requirement: bool | None = None
    lease_months: int | None = None
    citizenship: str | None = None
    has_passport: bool | None = None
    employer_support: bool | None = None
    notes: list[str] = Field(default_factory=list)


class ClientProfile(BaseModel):
    client_id: str
    full_name: str
    citizenship: str
    employment_type: str
    monthly_income: float
    income_currency: str = "USD"
    has_local_guarantor: bool = False
    has_passport: bool = True
    employer_support: bool = False
    household: Household = Field(default_factory=Household)
    notes: list[str] = Field(default_factory=list)


class RelocationCase(BaseModel):
    case_id: str
    client_id: str
    city: str
    country: str
    move_in_date: date
    office_zone: str | None = None
    monthly_budget: float
    upfront_budget: float | None = None
    max_commute_minutes: int | None = None
    preferred_districts: list[str] = Field(default_factory=list)
    furnished: bool | None = None
    rooms_min: int | None = None
    lease_months: int | None = None
    urgency_level: str = "normal"
    document_status: str = "complete"
    needs_school_access: bool = False
    notes: list[str] = Field(default_factory=list)


class Listing(BaseModel):
    listing_id: str
    city: str
    country: str
    district_id: str
    district_name: str
    title: str
    property_type: str
    monthly_rent: float
    currency: str = "USD"
    deposit_months: float = 1.0
    agency_fee: float = 0.0
    move_in_fee: float = 0.0
    utilities_monthly: float = 0.0
    area_sqm: float
    rooms: int
    available_from: date
    furnished: bool = True
    pet_friendly: bool = False
    max_pets: int | None = None
    children_friendly: bool = True
    elevator: bool | None = None
    floor: int | None = None
    max_occupants: int = 2
    commute_to_office_minutes: int | None = None
    commute_to_center_minutes: int | None = None
    min_lease_months: int = 12
    short_term_available: bool = False
    required_income_multiplier: float | None = None
    income_verification_required: bool = False
    notes: list[str] = Field(default_factory=list)
    landlord_flags: list[str] = Field(default_factory=list)


class District(BaseModel):
    district_id: str
    city: str
    country: str
    name: str
    avg_rent_from: float
    avg_rent_to: float
    is_central: bool = False
    family_friendly: bool = False
    pet_friendly: bool = False
    safety_score: float = 0.5
    school_score: float = 0.5
    transit_score: float = 0.5
    commute_to_center_minutes: int = 30
    description: str = ""


class City(BaseModel):
    name: str
    country: str
    median_rent: float
    cost_of_living: float
    commute_guidance: str
    popular_districts: list[str] = Field(default_factory=list)
    description: str = ""


class Country(BaseModel):
    name: str
    relocation_by_internal_passport: bool
    residence_orientation: str
    citizenship_orientation: str
    cost_of_living_single_range: str
    cost_of_living_family_range: str
    primary_city: str
    notes: list[str] = Field(default_factory=list)


class RelocationService(BaseModel):
    service_id: str
    city: str | None = None
    country: str | None = None
    service_type: str
    name: str
    cost: float
    currency: str = "USD"
    description: str
    suitable_for: list[str] = Field(default_factory=list)


class UpfrontCostEstimate(BaseModel):
    listing_id: str
    first_month: float
    deposit: float
    agency_fee: float
    move_in_fee: float
    utilities_reserve: float
    total: float
    currency: str = "USD"
    notes: list[str] = Field(default_factory=list)


class ScoredListing(BaseModel):
    listing: Listing
    total_score: float
    sub_scores: dict[str, float] = Field(default_factory=dict)
    pros: list[str] = Field(default_factory=list)
    cons: list[str] = Field(default_factory=list)
    constraint_violations: list[str] = Field(default_factory=list)
    estimated_upfront_cost: UpfrontCostEstimate


class DistrictRecommendation(BaseModel):
    district_id: str
    city: str
    rationale: str
    estimated_rent_range: str
    estimated_commute_minutes: int
    tradeoffs: list[str] = Field(default_factory=list)


class VerificationResult(BaseModel):
    status: Literal["approved", "clarification", "escalation", "rejected"]
    passed_checks: list[str] = Field(default_factory=list)
    failed_checks: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    required_user_clarifications: list[str] = Field(default_factory=list)


class FinalRecommendation(BaseModel):
    summary: str
    top_choices: list[ScoredListing] = Field(default_factory=list)
    alternatives: list[str] = Field(default_factory=list)
    important_notes: list[str] = Field(default_factory=list)
    clarifying_questions: list[str] = Field(default_factory=list)
    escalation_reason: str | None = None


class AgentState(BaseModel):
    user_message: str
    intent: Literal[
        "info",
        "search",
        "replanning",
        "preference_conflict",
        "budget_limit",
        "clarification",
        "escalation",
    ] | None = None

    client_id: str | None = None
    case_id: str | None = None
    client_profile: ClientProfile | None = None
    relocation_case: RelocationCase | None = None

    requirements: RentalRequirements | None = None
    previous_requirements: RentalRequirements | None = None
    changed_constraints: dict[str, Any] = Field(default_factory=dict)

    retrieved_policy_chunks: list[PolicyChunk] = Field(default_factory=list)
    candidate_listings: list[Listing] = Field(default_factory=list)
    ranked_listings: list[ScoredListing] = Field(default_factory=list)
    previous_ranked_listings: list[ScoredListing] = Field(default_factory=list)
    district_recommendations: list[DistrictRecommendation] = Field(default_factory=list)
    relocation_services: list[RelocationService] = Field(default_factory=list)
    city_info: City | None = None
    country_profile: Country | None = None

    verification_result: VerificationResult | None = None
    final_recommendation: FinalRecommendation | None = None
    final_answer: str | None = None

    replanning_notes: list[str] = Field(default_factory=list)
    replanning_tags: list[str] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    persistent_memory_loaded: bool = False
    persistent_memory_updated_at: str | None = None
    persistent_memory_summary: str | None = None
    warnings: list[str] = Field(default_factory=list)
    errors: list[str] = Field(default_factory=list)
