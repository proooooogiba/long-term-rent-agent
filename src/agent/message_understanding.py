from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel


class RouterDecision(BaseModel):
    intent: Literal[
        "info",
        "search",
        "replanning",
        "preference_conflict",
        "budget_limit",
        "clarification",
        "escalation",
    ]
    rationale: str | None = None


class IntakeExtraction(BaseModel):
    city: str | None = None
    country: str | None = None
    move_in_date: date | None = None
    monthly_budget: float | None = None
    budget_currency: str | None = None
    upfront_budget: float | None = None
    adults: int | None = None
    children: int | None = None
    pets: list[str] | None = None
    preferred_districts: list[str] | None = None
    office_zone: str | None = None
    max_commute_minutes: int | None = None
    rooms_min: int | None = None
    housing_type: str | None = None
    furnished: bool | None = None
    elevator: bool | None = None
    floor_max: int | None = None
    school_requirement: bool | None = None
    lease_months: int | None = None
    has_passport: bool | None = None
    employer_support: bool | None = None
    citizenship: str | None = None
    document_status: Literal["complete", "incomplete_docs"] | None = None
    center_preference: Literal["prefer_center", "center_not_required", "unspecified"] = "unspecified"
    office_dependency: bool = False
