"""Dependency-free simulation harness for EvalRoute's five required experiments."""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FIXTURE = ROOT / "fixtures" / "demo_observations.jsonl"
RESULTS = ROOT / "results"
DEFAULT = {"quality": .45, "latency": .20, "cost": .20, "reliability": .15}


def load_rows(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def normalized(rows: list[dict]) -> list[dict]:
    max_latency = max(row["latency_ms"] for row in rows) or 1
    max_cost = max(row["cost"] for row in rows) or 1
    return [{**row, "latency": 1 - row["latency_ms"] / max_latency,
             "cost_score": 1 - row["cost"] / max_cost, "reliability": float(row["success"])} for row in rows]


def score(row: dict, weights: dict[str, float]) -> float:
    return (row["quality"] * weights["quality"] + row["latency"] * weights["latency"]
            + row["cost_score"] * weights["cost"] + row["reliability"] * weights["reliability"])


def select(rows: list[dict], weights: dict[str, float], budget: float | None = None,
           unavailable: set[str] | None = None) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if (budget is None or row["cost"] <= budget) and row["model"] not in (unavailable or set()):
            groups[row["request"]].append(row)
    return [max(candidates, key=lambda item: score(item, weights)) for candidates in groups.values() if candidates]


def aggregate(chosen: list[dict]) -> dict:
    n = len(chosen) or 1
    return {"requests": len(chosen), "mean_quality": round(sum(x["quality"] for x in chosen) / n, 4),
            "mean_latency_ms": round(sum(x["latency_ms"] for x in chosen) / n, 2),
            "total_cost": round(sum(x["cost"] for x in chosen), 6),
            "success_rate": round(sum(x["success"] for x in chosen) / n, 4),
            "models": [x["model"] for x in chosen]}


def pareto_front(rows: list[dict]) -> list[str]:
    """Return non-dominated models over quality (max), latency (min), cost (min)."""
    by_model: dict[str, dict] = {}
    for model in {row["model"] for row in rows}:
        items = [row for row in rows if row["model"] == model]
        by_model[model] = {"quality": sum(x["quality"] for x in items) / len(items),
                           "latency": sum(x["latency_ms"] for x in items) / len(items),
                           "cost": sum(x["cost"] for x in items) / len(items)}
    front = []
    for model, metrics in by_model.items():
        dominated = any(
            other != model and candidate["quality"] >= metrics["quality"]
            and candidate["latency"] <= metrics["latency"] and candidate["cost"] <= metrics["cost"]
            and candidate != metrics for other, candidate in by_model.items()
        )
        if not dominated:
            front.append(model)
    return sorted(front)


def main() -> None:
    rows = normalized(load_rows(FIXTURE))
    static = [row for row in rows if row["model"] == "model-a"]
    policies = {
        "quality_first": {"quality": .70, "latency": .10, "cost": .05, "reliability": .15},
        "balanced": DEFAULT,
        "latency_first": {"quality": .25, "latency": .50, "cost": .10, "reliability": .15},
    }
    outputs = {
        "experiment_1_static_vs_adaptive": {"static": aggregate(static), "adaptive": aggregate(select(rows, DEFAULT))},
        "experiment_2_weight_sensitivity": {
            "policies": {name: aggregate(select(rows, weights)) for name, weights in policies.items()},
            "pareto_front": pareto_front(rows),
        },
        "experiment_3_cost_constraint": {"unconstrained": aggregate(select(rows, DEFAULT)),
                                           "max_0_006": aggregate(select(rows, DEFAULT, budget=.006))},
        "experiment_4_failure_injection": {"normal": aggregate(select(rows, DEFAULT)),
                                             "model_b_down": aggregate(select(rows, DEFAULT, unavailable={"model-b"}))},
    }
    drifted = [{**row, "quality": max(0, row["quality"] - .20) if row["model"] == "model-b" else row["quality"]} for row in rows]
    outputs["experiment_5_profile_drift"] = {"before": aggregate(select(rows, DEFAULT)), "after": aggregate(select(drifted, DEFAULT))}

    RESULTS.mkdir(parents=True, exist_ok=True)
    (RESULTS / "demo-results.json").write_text(json.dumps({"fixture": True, "experiments": outputs}, indent=2), encoding="utf-8")
    lines = ["# Demo experiment results", "", "> Synthetic fixture output; not an empirical benchmark.", ""]
    for name, result in outputs.items():
        lines.extend([f"## {name}", "", "```json", json.dumps(result, indent=2), "```", ""])
    (RESULTS / "demo-results.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {len(outputs)} experiment summaries to {RESULTS}")


if __name__ == "__main__":
    main()
