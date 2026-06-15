from __future__ import annotations

from src.evals.benchmark import BenchmarkTrialCaseResult, summarize_benchmark_results
from src.evals.metrics import CaseMetrics


def test_summarize_benchmark_results_tracks_reliability_and_pass_at_k(tmp_path):
    trial_results = [
        BenchmarkTrialCaseResult(
            trial_index=1,
            case_id="Q-001",
            relocation_case_id="R-0001",
            category="search",
            expected_outcome_type="recommendation",
            gate_passed=True,
            hard_gate_passed=True,
            soft_pass_rate=1.0,
            case_score=0.95,
            latency_ms=100.0,
            metrics={"intent_accuracy": 1.0},
            warnings=[],
        ),
        BenchmarkTrialCaseResult(
            trial_index=2,
            case_id="Q-001",
            relocation_case_id="R-0001",
            category="search",
            expected_outcome_type="recommendation",
            gate_passed=False,
            hard_gate_passed=False,
            soft_pass_rate=0.0,
            case_score=0.35,
            latency_ms=140.0,
            metrics={"intent_accuracy": 0.0},
            warnings=["benchmark_error:RuntimeError"],
            error="Connection error",
        ),
        BenchmarkTrialCaseResult(
            trial_index=1,
            case_id="Q-002",
            relocation_case_id=None,
            category="info",
            expected_outcome_type="info",
            gate_passed=True,
            hard_gate_passed=True,
            soft_pass_rate=1.0,
            case_score=0.9,
            latency_ms=90.0,
            metrics={"intent_accuracy": 1.0},
            warnings=[],
        ),
        BenchmarkTrialCaseResult(
            trial_index=2,
            case_id="Q-002",
            relocation_case_id=None,
            category="info",
            expected_outcome_type="info",
            gate_passed=True,
            hard_gate_passed=True,
            soft_pass_rate=1.0,
            case_score=0.88,
            latency_ms=95.0,
            metrics={"intent_accuracy": 1.0},
            warnings=[],
        ),
    ]
    rows = [
        CaseMetrics(1.0, None, 1.0, None, 1.0, None, 1.0, None, None, None),
        CaseMetrics(0.0, None, 0.0, None, 0.0, None, 0.0, None, None, None),
        CaseMetrics(1.0, None, None, None, None, None, None, None, None, 1.0),
        CaseMetrics(1.0, None, None, None, None, None, None, None, None, 1.0),
    ]

    summary = summarize_benchmark_results(
        trial_results,
        rows,
        qa_path=tmp_path / "qa.jsonl",
        llm_backend="openrouter",
        llm_mode="required",
        model="deepseek/deepseek-v3.2",
        trials=2,
    )

    assert summary.total_cases == 2
    assert summary.total_trial_runs == 4
    assert summary.mean_case_pass_rate == 0.75
    assert summary.case_pass_at_k == 1.0
    assert summary.case_pass_all_k == 0.5
    assert summary.case_outcome_consistency == 0.5
    assert summary.aggregate_quality_gate["passed"] is False
    assert summary.aggregate_metrics["pet_constraint_pass_rate"] is None
    assert summary.cases[0].case_id == "Q-001"
    assert summary.cases[0].pass_rate == 0.5
    assert summary.cases[1].case_id == "Q-002"
    assert summary.cases[1].pass_all_k == 1.0
