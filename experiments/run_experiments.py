"""Command-line entry point for reproducible offline routing experiments."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from routing_experiments import (
    Constraints,
    References,
    load_observations,
    run_suite,
    validate_empirical_profiles,
)


ROOT = Path(__file__).resolve().parent


def markdown_report(payload: dict) -> str:
    metadata = payload["metadata"]
    evidence = payload["evidence"]
    lines = [
        "# Routing experiment results",
        "",
        f"> Evidence level: **{evidence['level']}**. {evidence['warning']}",
        "",
        "## Run metadata",
        "",
        f"- Observations: {metadata['observation_rows']}",
        f"- Requests: {metadata['requests']}",
        f"- Models: {', '.join(metadata['models'])}",
        f"- Repeats: {metadata['repeats']}",
        "",
        "## Baseline comparison",
        "",
        "| Policy | Quality | Mean latency (ms) | P95 latency (ms) | Mean cost | Success | Violations | Utility |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for policy, result in payload["baseline_comparison"].items():
        metric = result["point_estimate"]
        lines.append(
            f"| {policy} | {metric['mean_quality']:.4f} | {metric['mean_latency_ms']:.2f} | "
            f"{metric['p95_latency_ms']:.2f} | {metric['mean_cost']:.6f} | "
            f"{metric['success_rate']:.4f} | {metric['constraint_violation_rate']:.4f} | "
            f"{metric['utility']:.4f} |"
        )
    for section in ("weight_sensitivity", "ablation", "failure_and_drift"):
        lines.extend(["", f"## {section.replace('_', ' ').title()}", "", "```json", json.dumps(payload[section], indent=2), "```"])
    lines.extend([
        "",
        "## Interpretation guardrail",
        "",
        "These numbers describe the supplied observation file only. A synthetic fixture verifies the evaluation code; "
        "it does not establish that EvalRoute improves real model quality, latency, cost, or reliability.",
        "",
    ])
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=ROOT / "fixtures" / "demo_observations.jsonl")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "results")
    parser.add_argument("--repeats", type=int, default=30)
    parser.add_argument("--latency-reference-ms", type=float, default=1000.0)
    parser.add_argument("--cost-reference", type=float, default=0.01)
    parser.add_argument("--max-latency-ms", type=float, default=1000.0)
    parser.add_argument("--max-cost", type=float, default=0.01)
    parser.add_argument("--evidence-level", choices=("synthetic_demo", "empirical"), default="synthetic_demo")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    input_bytes = args.input.read_bytes()
    rows = load_observations(input_bytes.decode("utf-8").splitlines())
    if args.evidence_level == "empirical":
        validate_empirical_profiles(rows)
    payload = run_suite(
        rows,
        repeats=args.repeats,
        references=References(args.latency_reference_ms, args.cost_reference),
        constraints=Constraints(args.max_cost, args.max_latency_ms),
    )
    payload["evidence"] = {
        "level": args.evidence_level,
        "source": str(args.input),
        "sha256": hashlib.sha256(input_bytes).hexdigest(),
        "warning": (
            "Synthetic fixture output; do not cite as an empirical model benchmark."
            if args.evidence_level == "synthetic_demo"
            else "Caller-labelled empirical input; verify dataset, model and collection provenance before citation."
        ),
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "demo-results.json"
    markdown_path = args.output_dir / "demo-results.md"
    json_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    markdown_path.write_text(markdown_report(payload), encoding="utf-8")
    print(f"Wrote {json_path} and {markdown_path}")


if __name__ == "__main__":
    main()
