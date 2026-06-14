from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class MetricThreshold:
    minimum: float
    hard_gate: bool = False
    rationale: str = ""


DEFAULT_QA_THRESHOLDS: dict[str, MetricThreshold] = {
    "intent_accuracy": MetricThreshold(0.85, rationale="Router should classify most requests correctly."),
    "required_fields_extracted": MetricThreshold(0.85, rationale="Intake should capture key search fields."),
    "budget_constraint_pass_rate": MetricThreshold(0.95, hard_gate=True, rationale="Top recommendation should almost never violate budget."),
    "pet_constraint_pass_rate": MetricThreshold(0.90, rationale="Pet constraints should be respected for relevant households."),
    "upfront_cost_correctness": MetricThreshold(0.95, hard_gate=True, rationale="Cost estimation should stay close to reference values."),
    "expected_entities_accuracy": MetricThreshold(0.75, rationale="User-facing answer should mention the expected shortlist entities."),
    "recommendation_has_rationale": MetricThreshold(0.95, hard_gate=True, rationale="Final answer must explain fit and trade-offs."),
    "clarification_correctness": MetricThreshold(0.90, hard_gate=True, rationale="Agent should ask for clarification instead of hallucinating."),
    "escalation_correctness": MetricThreshold(0.90, hard_gate=True, rationale="Risky scenarios should be escalated reliably."),
    "info_answer_has_sources": MetricThreshold(0.80, rationale="Informational answers should cite at least one supporting source."),
}

MIN_SOFT_PASS_RATE = 0.75


@dataclass(frozen=True)
class QualityGateCheck:
    metric: str
    actual: float
    minimum: float
    passed: bool
    hard_gate: bool
    rationale: str


@dataclass(frozen=True)
class QualityGateResult:
    passed: bool
    hard_gate_passed: bool
    soft_pass_rate: float
    minimum_soft_pass_rate: float
    checks: list[QualityGateCheck]


def evaluate_quality_gate(
    metrics: dict[str, float],
    thresholds: dict[str, MetricThreshold] | None = None,
    *,
    minimum_soft_pass_rate: float = MIN_SOFT_PASS_RATE,
) -> QualityGateResult:
    effective_thresholds = thresholds or DEFAULT_QA_THRESHOLDS
    checks: list[QualityGateCheck] = []
    hard_gate_passed = True
    soft_total = 0
    soft_passed = 0

    for metric, threshold in effective_thresholds.items():
        actual = float(metrics.get(metric, 0.0))
        passed = actual >= threshold.minimum
        checks.append(
            QualityGateCheck(
                metric=metric,
                actual=actual,
                minimum=threshold.minimum,
                passed=passed,
                hard_gate=threshold.hard_gate,
                rationale=threshold.rationale,
            )
        )
        if threshold.hard_gate:
            hard_gate_passed = hard_gate_passed and passed
        else:
            soft_total += 1
            if passed:
                soft_passed += 1

    soft_pass_rate = 1.0 if soft_total == 0 else round(soft_passed / soft_total, 4)
    passed = hard_gate_passed and soft_pass_rate >= minimum_soft_pass_rate
    return QualityGateResult(
        passed=passed,
        hard_gate_passed=hard_gate_passed,
        soft_pass_rate=soft_pass_rate,
        minimum_soft_pass_rate=minimum_soft_pass_rate,
        checks=checks,
    )
