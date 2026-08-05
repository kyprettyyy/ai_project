"""Offline policy evaluation for the EvalRoute research prototype.

The module is deliberately standard-library only.  It accepts one observation per
request/model pair, evaluates multiple routing policies on the same trace, and
reports quality, latency, cost, reliability, constraint violations and uncertainty.
"""

from __future__ import annotations

import math
import random
import statistics
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Callable, Iterable


DEFAULT_WEIGHTS = {
    "quality": 0.45,
    "latency": 0.20,
    "cost": 0.20,
    "reliability": 0.15,
}

WEIGHT_PRESETS = {
    "quality_first": {"quality": 0.70, "latency": 0.10, "cost": 0.05, "reliability": 0.15},
    "balanced": DEFAULT_WEIGHTS,
    "cost_first": {"quality": 0.25, "latency": 0.10, "cost": 0.50, "reliability": 0.15},
    "latency_first": {"quality": 0.25, "latency": 0.50, "cost": 0.10, "reliability": 0.15},
    "reliability_first": {"quality": 0.25, "latency": 0.10, "cost": 0.10, "reliability": 0.55},
}


@dataclass(frozen=True, slots=True)
class References:
    latency_ms: float = 1000.0
    cost_per_request: float = 0.01


@dataclass(frozen=True, slots=True)
class Constraints:
    max_cost: float | None = 0.01
    max_latency_ms: float | None = 1000.0


def load_observations(lines: Iterable[str]) -> list[dict]:
    import json

    rows = [json.loads(line) for line in lines if line.strip()]
    validate_observations(rows)
    return rows


def validate_observations(rows: list[dict]) -> None:
    required = {"request", "task", "model", "quality", "latency_ms", "cost", "success"}
    if not rows:
        raise ValueError("observation dataset is empty")
    seen: set[tuple[str, str]] = set()
    for index, row in enumerate(rows, start=1):
        missing = required - row.keys()
        if missing:
            raise ValueError(f"row {index} is missing: {', '.join(sorted(missing))}")
        key = (str(row["request"]), str(row["model"]))
        if key in seen:
            raise ValueError(f"duplicate request/model pair: {key[0]} / {key[1]}")
        seen.add(key)
        for field in ("quality", "latency_ms", "cost", "success"):
            value = float(row[field])
            if not math.isfinite(value):
                raise ValueError(f"row {index} has non-finite {field}")
        if not 0 <= float(row["quality"]) <= 1:
            raise ValueError(f"row {index} quality must be in [0, 1]")
        if not 0 <= float(row["success"]) <= 1:
            raise ValueError(f"row {index} success must be in [0, 1]")
        if float(row["latency_ms"]) < 0 or float(row["cost"]) < 0:
            raise ValueError(f"row {index} latency and cost must be non-negative")


def validate_empirical_profiles(rows: list[dict]) -> None:
    """Prevent held-out outcome leakage in runs labelled as empirical."""
    required = {"profile_quality", "profile_reliability", "profile_sample_count"}
    for index, row in enumerate(rows, start=1):
        missing = required - row.keys()
        if missing:
            raise ValueError(
                f"empirical row {index} is missing precomputed profile fields: "
                f"{', '.join(sorted(missing))}"
            )


def inverse_reference_score(value: float, reference: float) -> float:
    """Stable higher-is-better transform independent of the candidate set."""
    return 1.0 / (1.0 + max(0.0, float(value)) / max(0.000001, float(reference)))


def normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    values: dict[str, float] = {}
    for name in DEFAULT_WEIGHTS:
        try:
            value = float(weights.get(name, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        values[name] = value if math.isfinite(value) and value > 0 else 0.0
    total = sum(values.values())
    return dict(DEFAULT_WEIGHTS) if total <= 0 else {name: value / total for name, value in values.items()}


def row_score(row: dict, weights: dict[str, float], references: References) -> float:
    weights = normalize_weights(weights)
    sample_count = max(0, int(row.get("profile_sample_count", 20)))
    minimum_samples = max(1, int(row.get("minimum_profile_samples", 20)))
    age_days = max(0.0, float(row.get("profile_age_days", 0.0)))
    half_life = max(0.000001, float(row.get("profile_half_life_days", 30.0)))
    confidence = min(1.0, sample_count / minimum_samples) * math.exp2(-age_days / half_life)
    observed_quality = float(row.get("profile_quality", row["quality"]))
    adjusted_quality = max(0.0, min(1.0, observed_quality * confidence + 0.5 * (1 - confidence)))
    signals = {
        "quality": adjusted_quality,
        "latency": inverse_reference_score(float(row["latency_ms"]), references.latency_ms),
        "cost": inverse_reference_score(float(row["cost"]), references.cost_per_request),
        "reliability": float(row.get("profile_reliability", row["success"])),
    }
    return sum(weights[name] * signals[name] for name in DEFAULT_WEIGHTS)


def group_by_request(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row["request"])].append(row)
    return [(request, sorted(items, key=lambda item: str(item["model"]))) for request, items in sorted(grouped.items())]


def _model_means(rows: list[dict], field: str) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        values[str(row["model"])].append(float(row[field]))
    return {model: statistics.fmean(items) for model, items in values.items()}


def _eligible(rows: list[dict], constraints: Constraints, unavailable: set[str]) -> list[dict]:
    result = []
    for row in rows:
        if str(row["model"]) in unavailable:
            continue
        if constraints.max_cost is not None and float(row["cost"]) > constraints.max_cost:
            continue
        if constraints.max_latency_ms is not None and float(row["latency_ms"]) > constraints.max_latency_ms:
            continue
        result.append(row)
    return result


def select_policy(
    rows: list[dict],
    policy: str,
    *,
    weights: dict[str, float] | None = None,
    references: References = References(),
    constraints: Constraints = Constraints(),
    seed: int = 0,
    unavailable: set[str] | None = None,
) -> list[dict]:
    """Select exactly one available candidate for each request."""
    validate_observations(rows)
    unavailable = unavailable or set()
    rng = random.Random(seed)
    profile_rows = [
        {**row, "baseline_quality": row.get("profile_quality", row["quality"])}
        for row in rows
    ]
    baseline_quality = _model_means(profile_rows, "baseline_quality")
    strongest = max(baseline_quality, key=lambda model: (baseline_quality[model], model))
    cheapest = min(_model_means(rows, "cost"), key=lambda model: (_model_means(rows, "cost")[model], model))
    selected: list[dict] = []

    for request_index, (_, candidates) in enumerate(group_by_request(rows)):
        available = [row for row in candidates if str(row["model"]) not in unavailable]
        if not available:
            continue
        if policy == "fixed_strongest":
            chosen = next((row for row in available if row["model"] == strongest), max(available, key=lambda row: (row["quality"], row["model"])))
        elif policy == "fixed_cheapest":
            chosen = next((row for row in available if row["model"] == cheapest), min(available, key=lambda row: (row["cost"], row["model"])))
        elif policy == "random":
            chosen = rng.choice(available)
        elif policy == "round_robin":
            chosen = available[request_index % len(available)]
        elif policy == "cost_first":
            chosen = min(available, key=lambda row: (float(row["cost"]), -float(row["quality"]), str(row["model"])))
        elif policy == "latency_first":
            chosen = min(available, key=lambda row: (float(row["latency_ms"]), -float(row["quality"]), str(row["model"])))
        elif policy in {"static_weighted", "evalroute_feedback"}:
            pool = _eligible(available, constraints, set()) if policy == "evalroute_feedback" else available
            if not pool:
                continue
            chosen = max(
                pool,
                key=lambda row: (row_score(row, weights or DEFAULT_WEIGHTS, references), str(row["model"])),
            )
        else:
            raise ValueError(f"unknown policy: {policy}")
        selected.append(chosen)
    return selected


def percentile(values: list[float], percentile_value: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile_value * len(ordered)))
    return ordered[min(len(ordered), rank) - 1]


def aggregate(chosen: list[dict], constraints: Constraints = Constraints()) -> dict:
    if not chosen:
        return {
            "requests": 0, "mean_quality": 0.0, "mean_latency_ms": 0.0,
            "p95_latency_ms": 0.0, "mean_cost": 0.0, "total_cost": 0.0,
            "success_rate": 0.0, "constraint_violation_rate": 0.0,
            "utility": 0.0, "model_distribution": {},
        }
    n = len(chosen)
    qualities = [float(row["quality"]) for row in chosen]
    latencies = [float(row["latency_ms"]) for row in chosen]
    costs = [float(row["cost"]) for row in chosen]
    successes = [float(row["success"]) for row in chosen]
    violations = [
        (constraints.max_cost is not None and cost > constraints.max_cost)
        or (constraints.max_latency_ms is not None and latency > constraints.max_latency_ms)
        for cost, latency in zip(costs, latencies)
    ]
    utility_values = [quality - 0.15 * (latency / 1000.0) - 10.0 * cost for quality, latency, cost in zip(qualities, latencies, costs)]
    counts = Counter(str(row["model"]) for row in chosen)
    return {
        "requests": n,
        "mean_quality": round(statistics.fmean(qualities), 4),
        "mean_latency_ms": round(statistics.fmean(latencies), 2),
        "p95_latency_ms": round(percentile(latencies, 0.95), 2),
        "mean_cost": round(statistics.fmean(costs), 6),
        "total_cost": round(sum(costs), 6),
        "success_rate": round(statistics.fmean(successes), 4),
        "constraint_violation_rate": round(sum(violations) / n, 4),
        "utility": round(statistics.fmean(utility_values), 4),
        "model_distribution": {model: round(count / n, 4) for model, count in sorted(counts.items())},
    }


def summarize_trials(trials: list[dict]) -> dict:
    summary: dict[str, dict[str, float]] = {}
    for metric in ("mean_quality", "mean_latency_ms", "p95_latency_ms", "mean_cost", "success_rate", "constraint_violation_rate", "utility"):
        values = [float(trial[metric]) for trial in trials]
        mean = statistics.fmean(values)
        stddev = statistics.stdev(values) if len(values) > 1 else 0.0
        half_width = 1.96 * stddev / math.sqrt(len(values)) if values else 0.0
        summary[metric] = {
            "mean": round(mean, 6),
            "stddev": round(stddev, 6),
            "ci95_low": round(mean - half_width, 6),
            "ci95_high": round(mean + half_width, 6),
        }
    return summary


def pareto_front(rows: list[dict]) -> list[str]:
    metrics = {
        model: {
            "quality": _model_means(rows, "quality")[model],
            "latency": _model_means(rows, "latency_ms")[model],
            "cost": _model_means(rows, "cost")[model],
        }
        for model in _model_means(rows, "quality")
    }
    front = []
    for model, value in metrics.items():
        dominated = any(
            other != model
            and candidate["quality"] >= value["quality"]
            and candidate["latency"] <= value["latency"]
            and candidate["cost"] <= value["cost"]
            and candidate != value
            for other, candidate in metrics.items()
        )
        if not dominated:
            front.append(model)
    return sorted(front)


def transform(rows: list[dict], predicate: Callable[[dict], bool], **changes: float) -> list[dict]:
    output = []
    for row in rows:
        updated = dict(row)
        if predicate(row):
            for key, value in changes.items():
                updated[key] = value
        output.append(updated)
    return output


def run_suite(
    rows: list[dict],
    *,
    repeats: int = 30,
    references: References = References(),
    constraints: Constraints = Constraints(),
) -> dict:
    validate_observations(rows)
    repeats = max(2, int(repeats))
    policies = [
        "fixed_strongest", "fixed_cheapest", "random", "round_robin",
        "cost_first", "latency_first", "static_weighted", "evalroute_feedback",
    ]
    baseline_trials = {
        policy: [
            aggregate(select_policy(rows, policy, references=references, constraints=constraints, seed=seed), constraints)
            for seed in range(repeats if policy == "random" else 2)
        ]
        for policy in policies
    }
    sensitivity = {
        name: aggregate(
            select_policy(rows, "evalroute_feedback", weights=weights, references=references, constraints=constraints),
            constraints,
        )
        for name, weights in WEIGHT_PRESETS.items()
    }
    ablations = {
        f"without_{dimension}": aggregate(
            select_policy(
                rows,
                "evalroute_feedback",
                weights={**DEFAULT_WEIGHTS, dimension: 0.0},
                references=references,
                constraints=constraints,
            ),
            constraints,
        )
        for dimension in DEFAULT_WEIGHTS
    }
    models = sorted({str(row["model"]) for row in rows})
    target = models[len(models) // 2]
    latency_spike = transform(rows, lambda row: row["model"] == target, latency_ms=references.latency_ms * 3)
    price_spike = transform(rows, lambda row: row["model"] == target, cost=references.cost_per_request * 3)
    quality_drop = transform(rows, lambda row: row["model"] == target, quality=0.3, profile_quality=0.3)
    stale_profile = transform(rows, lambda row: row["model"] == target, profile_age_days=90.0)
    low_sample = transform(rows, lambda row: row["model"] == target, profile_sample_count=1)

    def evaluated(dataset: list[dict], unavailable: set[str] | None = None) -> dict:
        return aggregate(
            select_policy(
                dataset, "evalroute_feedback", references=references,
                constraints=constraints, unavailable=unavailable,
            ),
            constraints,
        )

    return {
        "metadata": {
            "observation_rows": len(rows),
            "requests": len({row["request"] for row in rows}),
            "models": models,
            "repeats": repeats,
            "references": {"latency_ms": references.latency_ms, "cost_per_request": references.cost_per_request},
            "constraints": {"max_cost": constraints.max_cost, "max_latency_ms": constraints.max_latency_ms},
        },
        "baseline_comparison": {
            policy: {"point_estimate": trials[0], "stability": summarize_trials(trials)}
            for policy, trials in baseline_trials.items()
        },
        "weight_sensitivity": sensitivity,
        "ablation": ablations,
        "failure_and_drift": {
            "normal": evaluated(rows),
            f"{target}_unavailable": evaluated(rows, {target}),
            f"{target}_latency_spike": evaluated(latency_spike),
            f"{target}_price_spike": evaluated(price_spike),
            f"{target}_quality_drop": evaluated(quality_drop),
            f"{target}_stale_profile": evaluated(stale_profile),
            f"{target}_low_sample": evaluated(low_sample),
        },
        "pareto_front": pareto_front(rows),
    }
