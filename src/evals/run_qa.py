from __future__ import annotations

import argparse
from pathlib import Path
import sys

from src.agent.graph import RelocationAgent
from src.db.seed import DEFAULT_DB_PATH, seed_database
from src.evals.metrics import aggregate_metrics, evaluate_case, load_jsonl, load_reference_upfront_costs
from src.evals.quality_gate import evaluate_quality_gate


ROOT_DIR = Path(__file__).resolve().parents[2]
QA_PATH = ROOT_DIR / "data" / "qa" / "qa.jsonl"


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run relocation-agent QA cases and evaluate the quality gate.")
    parser.add_argument(
        "--enforce-gate",
        action="store_true",
        help="Exit with code 1 when the quality gate does not pass.",
    )
    args = parser.parse_args(argv)

    seed_database(DEFAULT_DB_PATH)
    agent = RelocationAgent()
    reference_costs = load_reference_upfront_costs()
    qa_cases = load_jsonl(QA_PATH)

    rows = []
    for case in qa_cases:
        state = agent.run(case["user_request"], case_id=case.get("relocation_case_id"))
        rows.append(evaluate_case(case, state, reference_costs))

    metrics = aggregate_metrics(rows)
    print("QA metrics:")
    for key, value in metrics.items():
        print(f"- {key}: {value:.4f}")

    gate = evaluate_quality_gate(metrics)
    print("\nQuality gate:")
    print(f"- passed: {'yes' if gate.passed else 'no'}")
    print(f"- hard_gate_passed: {'yes' if gate.hard_gate_passed else 'no'}")
    print(f"- soft_pass_rate: {gate.soft_pass_rate:.2%} (minimum {gate.minimum_soft_pass_rate:.0%})")
    for check in gate.checks:
        gate_type = "hard" if check.hard_gate else "soft"
        status = "PASS" if check.passed else "FAIL"
        print(
            f"- [{status}] {check.metric}: actual={check.actual:.4f}, target>={check.minimum:.4f}, type={gate_type}"
        )

    if args.enforce_gate and not gate.passed:
        print("\nQuality gate failed, exiting with code 1.", file=sys.stderr)
        raise SystemExit(1)


if __name__ == "__main__":
    main()
