from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from src.evals.benchmark import DEFAULT_QA_PATH, run_benchmark, summary_to_dict


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run repeated relocation-agent benchmark trials for demo_stub or live OpenRouter models."
    )
    parser.add_argument(
        "--qa-path",
        type=Path,
        default=DEFAULT_QA_PATH,
        help="Path to the benchmark dataset in JSONL format.",
    )
    parser.add_argument(
        "--llm-backend",
        choices=("demo_stub", "openrouter"),
        default="openrouter",
        help="Which backend to benchmark.",
    )
    parser.add_argument(
        "--llm-mode",
        choices=("auto", "required"),
        default="required",
        help="Whether benchmark runs may fall back from the live LLM path.",
    )
    parser.add_argument(
        "--model",
        default=None,
        help="Optional OpenRouter model override, e.g. deepseek/deepseek-v3.2.",
    )
    parser.add_argument(
        "--trials",
        type=int,
        default=3,
        help="How many repeated runs to execute for each benchmark case.",
    )
    parser.add_argument(
        "--case-id",
        action="append",
        dest="case_ids",
        default=None,
        help="Optional benchmark case_id filter. Repeat the flag to run several specific cases.",
    )
    parser.add_argument(
        "--output-json",
        type=Path,
        default=None,
        help="Optional path to save the full benchmark report as JSON.",
    )
    parser.add_argument(
        "--enforce-gate",
        action="store_true",
        help="Exit with code 1 when the aggregate quality gate does not pass.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = _parse_args(argv)
    summary = run_benchmark(
        qa_path=args.qa_path,
        llm_backend=args.llm_backend,
        llm_mode=args.llm_mode,
        model=args.model,
        trials=args.trials,
        case_ids=args.case_ids,
    )

    print("Benchmark config:")
    print(f"- qa_path: {summary.qa_path}")
    print(f"- llm_backend: {summary.llm_backend}")
    print(f"- llm_mode: {summary.llm_mode}")
    print(f"- model: {summary.model}")
    print(f"- trials: {summary.trials}")
    print(f"- total_cases: {summary.total_cases}")
    print(f"- total_trial_runs: {summary.total_trial_runs}")

    print("\nAggregate metrics:")
    for key, value in summary.aggregate_metrics.items():
        if value is None:
            print(f"- {key}: n/a")
            continue
        print(f"- {key}: {value:.4f}")

    gate = summary.aggregate_quality_gate
    print("\nAggregate quality gate:")
    print(f"- passed: {'yes' if gate['passed'] else 'no'}")
    print(f"- hard_gate_passed: {'yes' if gate['hard_gate_passed'] else 'no'}")
    print(f"- soft_pass_rate: {gate['soft_pass_rate']:.2%} (minimum {gate['minimum_soft_pass_rate']:.0%})")

    print("\nBenchmark aggregates:")
    print(f"- mean_case_pass_rate: {summary.mean_case_pass_rate:.4f}")
    print(f"- case_pass_at_k: {summary.case_pass_at_k:.4f}")
    print(f"- case_pass_all_k: {summary.case_pass_all_k:.4f}")
    print(f"- case_outcome_consistency: {summary.case_outcome_consistency:.4f}")
    print(f"- mean_case_score: {summary.mean_case_score:.4f}")
    print(f"- mean_latency_ms: {summary.mean_latency_ms:.1f}")
    print(f"- p95_latency_ms: {summary.p95_latency_ms:.1f}")

    print("\nPer-case summary:")
    for case in summary.cases:
        print(
            f"- {case.case_id}: pass_rate={case.pass_rate:.4f}, "
            f"pass_at_k={case.pass_at_k:.0f}, pass_all_k={case.pass_all_k:.0f}, "
            f"consistency={case.outcome_consistency:.0f}, score={case.mean_case_score:.4f}, "
            f"latency_ms={case.mean_latency_ms:.1f}"
        )

    if args.output_json is not None:
        args.output_json.parent.mkdir(parents=True, exist_ok=True)
        args.output_json.write_text(
            json.dumps(summary_to_dict(summary), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"\nSaved JSON report to {args.output_json}")

    if args.enforce_gate and not bool(gate["passed"]):
        print("\nAggregate quality gate failed, exiting with code 1.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
