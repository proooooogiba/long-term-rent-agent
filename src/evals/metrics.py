from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path

from src.agent.state import AgentState


ROOT_DIR = Path(__file__).resolve().parents[2]
REFERENCE_DIR = ROOT_DIR / "data" / "reference"


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_reference_upfront_costs() -> dict[str, float]:
    mapping: dict[str, float] = {}

    listing_csv = REFERENCE_DIR / "listing_recommendations.csv"
    with listing_csv.open("r", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            mapping[row["recommended_listing_id"]] = float(row["estimated_upfront_cost_usd"])

    for row in load_jsonl(REFERENCE_DIR / "change_requests_gold.jsonl"):
        if row.get("updated_listing_id"):
            mapping[row["updated_listing_id"]] = float(row["estimated_upfront_cost_usd"])

    return mapping


def expected_intent(case: dict) -> str:
    category = case["category"]
    if category == "edge_case":
        return "info" if case["expected_outcome_type"] == "info" else "search"
    return category


@dataclass
class CaseMetrics:
    intent_accuracy: float
    required_fields_extracted: float | None
    budget_constraint_pass_rate: float | None
    pet_constraint_pass_rate: float | None
    upfront_cost_correctness: float | None
    expected_entities_accuracy: float | None
    recommendation_has_rationale: float | None
    clarification_correctness: float | None
    escalation_correctness: float | None
    info_answer_has_sources: float | None


def _expected_entities_accuracy(case: dict, state: AgentState) -> float | None:
    expected = case.get("expected_entities") or {}
    if not expected:
        return None

    top = state.ranked_listings[0] if state.ranked_listings else None
    checks: list[float] = []

    listing_id = expected.get("listing_id")
    if listing_id is not None:
        checks.append(1.0 if top and top.listing.listing_id == listing_id else 0.0)

    district_id = expected.get("district_id")
    if district_id is not None:
        candidate_district_ids: set[str] = set()
        if top:
            candidate_district_ids.add(top.listing.district_id)
        candidate_district_ids.update(item.listing.district_id for item in state.ranked_listings[:3])
        candidate_district_ids.update(item.district_id for item in state.district_recommendations[:3])
        if state.requirements:
            candidate_district_ids.update(state.requirements.preferred_districts)
        checks.append(1.0 if district_id in candidate_district_ids else 0.0)

    service_id = expected.get("service_id")
    if service_id is not None:
        checks.append(1.0 if any(service.service_id == service_id for service in state.relocation_services[:3]) else 0.0)

    return sum(checks) / len(checks) if checks else None


def evaluate_case(case: dict, state: AgentState, reference_costs: dict[str, float]) -> CaseMetrics:
    req = state.requirements
    top = state.ranked_listings[0] if state.ranked_listings else None
    verification_status = state.verification_result.status if state.verification_result else None

    intent_ok = 1.0 if state.intent == expected_intent(case) else 0.0

    fields_ok = None
    if req is not None and case["expected_outcome_type"] in {"recommendation", "clarification"}:
        critical = [
            bool(req.city),
            bool(req.move_in_date),
            req.monthly_budget is not None,
            bool(req.household.adults),
            bool(req.rooms_min or req.housing_type),
        ]
        fields_ok = sum(critical) / len(critical)

    budget_ok = None
    if case["expected_outcome_type"] == "recommendation" and top and req and req.monthly_budget is not None:
        budget_ok = 1.0 if top.listing.monthly_rent <= req.monthly_budget else 0.0

    pet_ok = None
    if case["expected_outcome_type"] == "recommendation" and top and req and req.household.pet_count > 0:
        pet_ok = 1.0 if top.listing.pet_friendly else 0.0

    upfront_ok = None
    if case["expected_outcome_type"] == "recommendation" and top:
        expected_cost = reference_costs.get(top.listing.listing_id)
        if expected_cost is None:
            upfront_ok = 1.0
        else:
            upfront_ok = 1.0 if abs(top.estimated_upfront_cost.total - expected_cost) <= 5 else 0.0

    entities_ok = _expected_entities_accuracy(case, state)

    rationale_ok = None
    if case["expected_outcome_type"] == "recommendation":
        rationale_ok = 1.0 if ("Почему подходит:" in (state.final_answer or "") and "Риски/компромиссы:" in (state.final_answer or "")) else 0.0

    clarification_ok = None
    if case["expected_outcome_type"] == "clarification":
        clarification_ok = 1.0 if verification_status == "clarification" else 0.0

    escalation_ok = None
    if case["expected_outcome_type"] == "escalation":
        escalation_ok = 1.0 if verification_status == "escalation" and "передать человеку" in (state.final_answer or "") else 0.0

    info_sources_ok = None
    if case["expected_outcome_type"] == "info":
        info_sources_ok = 1.0 if "Источники:" in (state.final_answer or "") else 0.0

    return CaseMetrics(
        intent_accuracy=intent_ok,
        required_fields_extracted=fields_ok,
        budget_constraint_pass_rate=budget_ok,
        pet_constraint_pass_rate=pet_ok,
        upfront_cost_correctness=upfront_ok,
        expected_entities_accuracy=entities_ok,
        recommendation_has_rationale=rationale_ok,
        clarification_correctness=clarification_ok,
        escalation_correctness=escalation_ok,
        info_answer_has_sources=info_sources_ok,
    )


def aggregate_metrics(rows: list[CaseMetrics]) -> dict[str, float]:
    if not rows:
        return {}
    keys = rows[0].__dataclass_fields__.keys()
    aggregated: dict[str, float] = {}
    for key in keys:
        values = [getattr(row, key) for row in rows if getattr(row, key) is not None]
        aggregated[key] = round(sum(values) / len(values), 4) if values else 0.0
    return aggregated
