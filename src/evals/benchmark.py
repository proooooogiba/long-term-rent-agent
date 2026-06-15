from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import mean
from tempfile import TemporaryDirectory
from time import perf_counter
from typing import Literal

from src.agent.dependencies import GraphDependencies
from src.agent.graph import AgentGraph, AgentTraceStep, RelocationAgent
from src.agent.llm import OpenRouterStructuredLLM
from src.db.seed import seed_database
from src.evals.metrics import (
    CaseMetrics,
    evaluate_case,
    load_jsonl,
    load_reference_upfront_costs,
)
from src.evals.quality_gate import QualityGateResult, evaluate_quality_gate
from src.tools.calculations import CalculationTools
from src.tools.relocation_db import RelocationDBTools


ROOT_DIR = Path(__file__).resolve().parents[2]
DEFAULT_QA_PATH = ROOT_DIR / "data" / "qa" / "qa.jsonl"


@dataclass(frozen=True)
class BenchmarkTrialCaseResult:
    trial_index: int
    case_id: str
    relocation_case_id: str | None
    category: str
    expected_outcome_type: str
    gate_passed: bool
    hard_gate_passed: bool
    soft_pass_rate: float
    case_score: float
    latency_ms: float
    metrics: dict[str, float | None]
    warnings: list[str]
    error: str | None = None


@dataclass(frozen=True)
class BenchmarkCaseSummary:
    case_id: str
    category: str
    expected_outcome_type: str
    trials: int
    pass_rate: float
    pass_at_k: float
    pass_all_k: float
    outcome_consistency: float
    mean_case_score: float
    mean_latency_ms: float


@dataclass(frozen=True)
class BenchmarkSummary:
    qa_path: str
    llm_backend: str
    llm_mode: str
    model: str
    trials: int
    total_cases: int
    total_trial_runs: int
    aggregate_metrics: dict[str, float | None]
    aggregate_quality_gate: dict[str, object]
    mean_case_pass_rate: float
    case_pass_at_k: float
    case_pass_all_k: float
    case_outcome_consistency: float
    mean_case_score: float
    mean_latency_ms: float
    p95_latency_ms: float
    cases: list[BenchmarkCaseSummary]
    trial_results: list[BenchmarkTrialCaseResult]


def case_metrics_to_dict(metrics: CaseMetrics) -> dict[str, float | None]:
    return {field_name: getattr(metrics, field_name) for field_name in metrics.__dataclass_fields__}


def _build_failed_case_metrics(case: dict[str, object]) -> CaseMetrics:
    expected_outcome_type = str(case["expected_outcome_type"])
    expected_entities = case.get("expected_entities") or {}
    expects_recommendation = expected_outcome_type == "recommendation"
    expects_clarification = expected_outcome_type == "clarification"
    expects_escalation = expected_outcome_type == "escalation"
    expects_info = expected_outcome_type == "info"
    expects_entities = bool(expected_entities)

    return CaseMetrics(
        intent_accuracy=0.0,
        required_fields_extracted=0.0 if expected_outcome_type in {"recommendation", "clarification"} else None,
        budget_constraint_pass_rate=0.0 if expects_recommendation else None,
        pet_constraint_pass_rate=0.0 if expects_recommendation else None,
        upfront_cost_correctness=0.0 if expects_recommendation else None,
        expected_entities_accuracy=0.0 if expects_entities else None,
        recommendation_has_rationale=0.0 if expects_recommendation else None,
        clarification_correctness=0.0 if expects_clarification else None,
        escalation_correctness=0.0 if expects_escalation else None,
        info_answer_has_sources=0.0 if expects_info else None,
    )


def _case_score(metrics: dict[str, float | None]) -> float:
    values = [value for value in metrics.values() if value is not None]
    return round(sum(values) / len(values), 4) if values else 0.0


def _latency_p95(latencies: list[float]) -> float:
    if not latencies:
        return 0.0
    ordered = sorted(latencies)
    index = max(0, int(round(0.95 * (len(ordered) - 1))))
    return round(ordered[index], 1)


def _quality_gate_to_dict(result: QualityGateResult) -> dict[str, object]:
    return {
        "passed": result.passed,
        "hard_gate_passed": result.hard_gate_passed,
        "soft_pass_rate": result.soft_pass_rate,
        "minimum_soft_pass_rate": result.minimum_soft_pass_rate,
        "checks": [
            {
                "metric": check.metric,
                "actual": check.actual,
                "minimum": check.minimum,
                "passed": check.passed,
                "hard_gate": check.hard_gate,
                "rationale": check.rationale,
            }
            for check in result.checks
        ],
    }


def _aggregate_metrics_preserving_missing(rows: list[CaseMetrics]) -> dict[str, float | None]:
    if not rows:
        return {}
    keys = rows[0].__dataclass_fields__.keys()
    aggregated: dict[str, float | None] = {}
    for key in keys:
        values = [getattr(row, key) for row in rows if getattr(row, key) is not None]
        aggregated[key] = round(sum(values) / len(values), 4) if values else None
    return aggregated


def _build_agent(
    db_path: Path,
    *,
    llm_backend: Literal["openrouter", "demo_stub"],
    llm_mode: Literal["auto", "required"],
    model: str | None,
) -> RelocationAgent:
    db_tools = RelocationDBTools(db_path)
    llm = OpenRouterStructuredLLM(model=model) if llm_backend == "openrouter" else None
    deps = GraphDependencies(
        db_tools=db_tools,
        calc_tools=CalculationTools(db_tools),
        llm=llm,
        llm_mode=llm_mode,
        llm_backend=llm_backend,
    )
    return RelocationAgent(graph=AgentGraph(deps=deps))


def run_benchmark(
    *,
    qa_path: Path = DEFAULT_QA_PATH,
    llm_backend: Literal["openrouter", "demo_stub"] = "openrouter",
    llm_mode: Literal["auto", "required"] = "required",
    model: str | None = None,
    trials: int = 3,
    case_ids: list[str] | None = None,
) -> BenchmarkSummary:
    if trials < 1:
        raise ValueError("trials must be >= 1")

    qa_cases = load_jsonl(qa_path)
    if case_ids:
        allowed = set(case_ids)
        qa_cases = [case for case in qa_cases if case["case_id"] in allowed]
    if not qa_cases:
        raise ValueError("benchmark suite is empty after filtering")
    reference_costs = load_reference_upfront_costs()
    trial_results: list[BenchmarkTrialCaseResult] = []
    rows: list[CaseMetrics] = []
    resolved_model = model or (OpenRouterStructuredLLM.DEFAULT_MODEL if llm_backend == "openrouter" else "demo_stub")

    for trial_index in range(1, trials + 1):
        with TemporaryDirectory(prefix=f"relocation-benchmark-{trial_index}-") as tmp_dir:
            db_path = seed_database(Path(tmp_dir) / "relocation.sqlite")
            agent = _build_agent(
                db_path,
                llm_backend=llm_backend,
                llm_mode=llm_mode,
                model=model,
            )
            for case in qa_cases:
                trace_steps: list[AgentTraceStep] = []
                started_at = perf_counter()
                error_message: str | None = None
                try:
                    state = agent.run(
                        case["user_request"],
                        case_id=case.get("relocation_case_id"),
                        trace_steps=trace_steps,
                    )
                    case_metrics = evaluate_case(case, state, reference_costs)
                    warnings = state.warnings
                except Exception as exc:  # pragma: no cover - live network/runtime failures are environment-specific
                    case_metrics = _build_failed_case_metrics(case)
                    warnings = [f"benchmark_error:{exc.__class__.__name__}"]
                    error_message = str(exc)
                latency_ms = round((perf_counter() - started_at) * 1000, 1)
                rows.append(case_metrics)

                metrics_dict = case_metrics_to_dict(case_metrics)
                gate = evaluate_quality_gate(metrics_dict, skip_missing_metrics=True)
                trial_results.append(
                    BenchmarkTrialCaseResult(
                        trial_index=trial_index,
                        case_id=case["case_id"],
                        relocation_case_id=case.get("relocation_case_id"),
                        category=case["category"],
                        expected_outcome_type=case["expected_outcome_type"],
                        gate_passed=gate.passed,
                        hard_gate_passed=gate.hard_gate_passed,
                        soft_pass_rate=gate.soft_pass_rate,
                        case_score=_case_score(metrics_dict),
                        latency_ms=latency_ms,
                        metrics=metrics_dict,
                        warnings=warnings,
                        error=error_message,
                    )
                )

    return summarize_benchmark_results(
        trial_results,
        rows,
        qa_path=qa_path,
        llm_backend=llm_backend,
        llm_mode=llm_mode,
        model=resolved_model,
        trials=trials,
    )


def summarize_benchmark_results(
    trial_results: list[BenchmarkTrialCaseResult],
    rows: list[CaseMetrics],
    *,
    qa_path: Path,
    llm_backend: str,
    llm_mode: str,
    model: str,
    trials: int,
) -> BenchmarkSummary:
    aggregate = _aggregate_metrics_preserving_missing(rows)
    aggregate_gate = evaluate_quality_gate(aggregate, skip_missing_metrics=True)

    grouped: dict[str, list[BenchmarkTrialCaseResult]] = {}
    for result in trial_results:
        grouped.setdefault(result.case_id, []).append(result)

    case_summaries: list[BenchmarkCaseSummary] = []
    for case_id, items in grouped.items():
        items = sorted(items, key=lambda item: item.trial_index)
        passes = [1.0 if item.gate_passed else 0.0 for item in items]
        pass_rate = round(sum(passes) / len(passes), 4)
        case_summaries.append(
            BenchmarkCaseSummary(
                case_id=case_id,
                category=items[0].category,
                expected_outcome_type=items[0].expected_outcome_type,
                trials=len(items),
                pass_rate=pass_rate,
                pass_at_k=1.0 if any(passes) else 0.0,
                pass_all_k=1.0 if all(passes) else 0.0,
                outcome_consistency=1.0 if pass_rate in {0.0, 1.0} else 0.0,
                mean_case_score=round(mean(item.case_score for item in items), 4),
                mean_latency_ms=round(mean(item.latency_ms for item in items), 1),
            )
        )
    case_summaries.sort(key=lambda item: item.case_id)

    latencies = [result.latency_ms for result in trial_results]
    return BenchmarkSummary(
        qa_path=str(qa_path),
        llm_backend=llm_backend,
        llm_mode=llm_mode,
        model=model,
        trials=trials,
        total_cases=len(case_summaries),
        total_trial_runs=len(trial_results),
        aggregate_metrics=aggregate,
        aggregate_quality_gate=_quality_gate_to_dict(aggregate_gate),
        mean_case_pass_rate=round(mean(item.pass_rate for item in case_summaries), 4) if case_summaries else 0.0,
        case_pass_at_k=round(mean(item.pass_at_k for item in case_summaries), 4) if case_summaries else 0.0,
        case_pass_all_k=round(mean(item.pass_all_k for item in case_summaries), 4) if case_summaries else 0.0,
        case_outcome_consistency=round(mean(item.outcome_consistency for item in case_summaries), 4)
        if case_summaries
        else 0.0,
        mean_case_score=round(mean(item.mean_case_score for item in case_summaries), 4) if case_summaries else 0.0,
        mean_latency_ms=round(mean(latencies), 1) if latencies else 0.0,
        p95_latency_ms=_latency_p95(latencies),
        cases=case_summaries,
        trial_results=trial_results,
    )


def summary_to_dict(summary: BenchmarkSummary) -> dict[str, object]:
    return asdict(summary)
