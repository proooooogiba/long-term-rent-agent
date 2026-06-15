from __future__ import annotations

from src.evals.quality_gate import DEFAULT_QA_THRESHOLDS, evaluate_quality_gate


def test_quality_gate_passes_when_hard_gates_and_soft_ratio_pass():
    metrics = {
        "intent_accuracy": 0.9,
        "required_fields_extracted": 0.9,
        "budget_constraint_pass_rate": 1.0,
        "pet_constraint_pass_rate": 0.9,
        "upfront_cost_correctness": 1.0,
        "expected_entities_accuracy": 0.8,
        "recommendation_has_rationale": 1.0,
        "clarification_correctness": 1.0,
        "escalation_correctness": 1.0,
        "info_answer_has_sources": 0.9,
    }

    result = evaluate_quality_gate(metrics)

    assert result.passed is True
    assert result.hard_gate_passed is True


def test_quality_gate_fails_when_hard_gate_metric_drops_below_threshold():
    metrics = {
        metric: threshold.minimum
        for metric, threshold in DEFAULT_QA_THRESHOLDS.items()
    }
    metrics["escalation_correctness"] = 0.5

    result = evaluate_quality_gate(metrics)

    assert result.passed is False
    assert result.hard_gate_passed is False
    escalation_check = next(check for check in result.checks if check.metric == "escalation_correctness")
    assert escalation_check.passed is False


def test_quality_gate_can_skip_non_applicable_metrics():
    metrics = {
        "intent_accuracy": 1.0,
        "required_fields_extracted": None,
        "budget_constraint_pass_rate": 1.0,
        "pet_constraint_pass_rate": None,
        "upfront_cost_correctness": 1.0,
        "expected_entities_accuracy": None,
        "recommendation_has_rationale": 1.0,
        "clarification_correctness": None,
        "escalation_correctness": None,
        "info_answer_has_sources": None,
    }

    result = evaluate_quality_gate(metrics, skip_missing_metrics=True)

    assert result.passed is True
    assert {check.metric for check in result.checks} == {
        "intent_accuracy",
        "budget_constraint_pass_rate",
        "upfront_cost_correctness",
        "recommendation_has_rationale",
    }
