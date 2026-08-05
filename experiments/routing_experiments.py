"""Leakage-safe offline policy evaluation for EvalRoute.

Every row separates information available before routing (``profile_*``) from the
held-out result observed after invocation (``observed_*``). Static routing reads a
separate immutable prior file. EvalRoute feedback delegates selection to the same
seven-dimensional :class:`ExplainableRouter` used by the gateway.
"""

from __future__ import annotations

import json
import math
import random
import statistics
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Callable, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.gateway.app.routing.explainable_router import (  # noqa: E402
    DEFAULT_WEIGHTS as ROUTER_DEFAULT_WEIGHTS,
    CandidateSignals,
    ExplainableRouter,
    RoutingContext,
    parse_capabilities,
)


PRIMARY_DIMENSIONS = ("quality", "latency", "cost", "reliability")

WEIGHT_PRESETS = {
    "quality_first": {
        "quality": 0.55, "latency": 0.10, "cost": 0.10, "reliability": 0.10,
        "task": 0.05, "context": 0.05, "budget": 0.05,
    },
    "balanced": ROUTER_DEFAULT_WEIGHTS,
    "cost_first": {
        "quality": 0.20, "latency": 0.10, "cost": 0.40, "reliability": 0.10,
        "task": 0.05, "context": 0.05, "budget": 0.10,
    },
    "latency_first": {
        "quality": 0.20, "latency": 0.40, "cost": 0.10, "reliability": 0.10,
        "task": 0.05, "context": 0.10, "budget": 0.05,
    },
    "reliability_first": {
        "quality": 0.20, "latency": 0.10, "cost": 0.10, "reliability": 0.40,
        "task": 0.10, "context": 0.05, "budget": 0.05,
    },
}


@dataclass(frozen=True, slots=True)
class References:
    latency_ms: float = 1000.0
    cost_per_request: float = 0.01


@dataclass(frozen=True, slots=True)
class Constraints:
    max_cost: float | None = 0.01
    max_latency_ms: float | None = 1000.0


@dataclass(frozen=True, slots=True)
class StaticModelPrior:
    quality_prior: float
    latency_prior: float
    cost_prior: float
    reliability_prior: float
    priority: int = 100

    def signals(self) -> dict[str, float]:
        return {
            "quality": self.quality_prior,
            "latency": self.latency_prior,
            "cost": self.cost_prior,
            "reliability": self.reliability_prior,
        }


def load_observations(lines: Iterable[str]) -> list[dict]:
    rows = [json.loads(line) for line in lines if line.strip()]
    validate_observations(rows)
    return rows


def load_static_priors(payload: str | bytes | dict) -> dict[str, StaticModelPrior]:
    raw = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
    if not isinstance(raw, dict) or not raw:
        raise ValueError("static prior configuration must be a non-empty object")
    required = {"quality_prior", "latency_prior", "cost_prior", "reliability_prior"}
    priors: dict[str, StaticModelPrior] = {}
    for model, values in raw.items():
        if not isinstance(values, dict):
            raise ValueError(f"static prior for {model} must be an object")
        missing = required - values.keys()
        if missing:
            raise ValueError(f"static prior for {model} is missing: {', '.join(sorted(missing))}")
        numbers = {name: float(values[name]) for name in required}
        if any(not math.isfinite(value) or not 0 <= value <= 1 for value in numbers.values()):
            raise ValueError(f"static prior scores for {model} must be finite and in [0, 1]")
        priors[str(model)] = StaticModelPrior(
            **numbers,
            priority=int(values.get("priority", 100)),
        )
    return priors


def validate_observations(rows: list[dict]) -> None:
    required = {
        "request", "task", "model",
        "profile_quality", "profile_latency_ms", "profile_cost",
        "profile_reliability", "profile_sample_count", "profile_age_days",
        "observed_quality", "observed_latency_ms", "observed_cost", "observed_success",
    }
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
        numeric_fields = (
            "profile_quality", "profile_latency_ms", "profile_cost", "profile_reliability",
            "profile_sample_count", "profile_age_days", "observed_quality",
            "observed_latency_ms", "observed_cost", "observed_success",
        )
        values = {field: float(row[field]) for field in numeric_fields}
        if any(not math.isfinite(value) for value in values.values()):
            raise ValueError(f"row {index} contains a non-finite numeric value")
        for field in ("profile_quality", "profile_reliability", "observed_quality", "observed_success"):
            if not 0 <= values[field] <= 1:
                raise ValueError(f"row {index} {field} must be in [0, 1]")
        for field in (
            "profile_latency_ms", "profile_cost", "profile_sample_count", "profile_age_days",
            "observed_latency_ms", "observed_cost",
        ):
            if values[field] < 0:
                raise ValueError(f"row {index} {field} must be non-negative")


def validate_empirical_profiles(rows: list[dict]) -> None:
    """Reject legacy or partial schemas before an input can be labelled empirical."""
    validate_observations(rows)


def validate_static_priors(rows: list[dict], priors: dict[str, StaticModelPrior]) -> None:
    missing = sorted({str(row["model"]) for row in rows} - priors.keys())
    if missing:
        raise ValueError(f"static prior configuration is missing models: {', '.join(missing)}")


def inverse_reference_score(value: float, reference: float) -> float:
    """Stable higher-is-better transform independent of the candidate set."""
    return 1.0 / (1.0 + max(0.0, float(value)) / max(0.000001, float(reference)))


def normalize_primary_weights(weights: dict[str, float] | None) -> dict[str, float]:
    source = weights or ROUTER_DEFAULT_WEIGHTS
    values: dict[str, float] = {}
    for name in PRIMARY_DIMENSIONS:
        try:
            value = float(source.get(name, 0.0))
        except (TypeError, ValueError):
            value = 0.0
        values[name] = value if math.isfinite(value) and value > 0 else 0.0
    total = sum(values.values())
    if total <= 0:
        return normalize_primary_weights(ROUTER_DEFAULT_WEIGHTS)
    return {name: value / total for name, value in values.items()}


def static_prior_score(prior: StaticModelPrior, weights: dict[str, float] | None = None) -> float:
    """Score immutable model priors; observation rows are intentionally unavailable."""
    normalized = normalize_primary_weights(weights)
    signals = prior.signals()
    return sum(normalized[name] * signals[name] for name in PRIMARY_DIMENSIONS)


def group_by_request(rows: list[dict]) -> list[tuple[str, list[dict]]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        grouped[str(row["request"])].append(row)
    return [
        (request, sorted(items, key=lambda item: str(item["model"])))
        for request, items in sorted(grouped.items())
    ]


def _profile_candidate(
    row: dict,
    model_id: int,
    prior: StaticModelPrior,
    references: References,
) -> CandidateSignals:
    task = str(row["task"])
    return CandidateSignals(
        model_id=model_id,
        model_key=str(row["model"]),
        context_length=max(0, int(row.get("context_length", 32768))),
        input_price=Decimal("0"),
        output_price=Decimal("0"),
        avg_latency_ms=max(0, round(float(row["profile_latency_ms"]))),
        live_success_rate=float(row["profile_reliability"]),
        priority=int(row.get("priority", prior.priority)),
        capabilities=parse_capabilities(row.get("capabilities", {"chat", task})),
        quality_score=float(row["profile_quality"]),
        profile_latency_score=inverse_reference_score(row["profile_latency_ms"], references.latency_ms),
        profile_cost_score=inverse_reference_score(row["profile_cost"], references.cost_per_request),
        profile_reliability_score=float(row["profile_reliability"]),
        sample_count=max(0, int(row["profile_sample_count"])),
        profile_version=max(0, int(row.get("profile_version", 0))),
        profile_task_type=str(row.get("profile_task", task)),
        profile_age_days=max(0.0, float(row["profile_age_days"])),
        estimated_request_cost=Decimal(str(row["profile_cost"])),
        quality_prior_score=prior.quality_prior,
        latency_prior_score=prior.latency_prior,
        cost_prior_score=prior.cost_prior,
        reliability_prior_score=prior.reliability_prior,
    )


def _routing_context(row: dict, references: References, constraints: Constraints) -> RoutingContext:
    max_cost = None if constraints.max_cost is None else Decimal(str(constraints.max_cost))
    budget = row.get("budget_remaining")
    return RoutingContext(
        task_type=str(row["task"]),
        estimated_input_tokens=max(0, int(row.get("estimated_input_tokens", 0))),
        expected_output_tokens=max(0, int(row.get("expected_output_tokens", 1024))),
        max_request_cost=max_cost,
        budget_remaining=None if budget is None else Decimal(str(budget)),
        min_quality=None if row.get("min_quality") is None else float(row["min_quality"]),
        max_latency_ms=None if constraints.max_latency_ms is None else round(constraints.max_latency_ms),
        min_success_rate=(
            None if row.get("min_success_rate") is None else float(row["min_success_rate"])
        ),
        required_capabilities=parse_capabilities(row.get("required_capabilities")),
        minimum_profile_samples=max(1, int(row.get("minimum_profile_samples", 20))),
        latency_reference_ms=max(1, round(references.latency_ms)),
        cost_reference=Decimal(str(references.cost_per_request)),
        profile_half_life_days=max(0.000001, float(row.get("profile_half_life_days", 30.0))),
        quality_uncertainty_penalty=max(0.0, float(row.get("quality_uncertainty_penalty", 0.05))),
    )


def _select_evalroute(
    candidates: list[dict],
    priors: dict[str, StaticModelPrior],
    references: References,
    constraints: Constraints,
    weights: dict[str, float] | None,
) -> dict | None:
    signals = [
        _profile_candidate(row, index + 1, priors[str(row["model"])], references)
        for index, row in enumerate(candidates)
    ]
    plan = ExplainableRouter().rank(signals, _routing_context(candidates[0], references, constraints), weights)
    if plan.selected is None:
        return None
    return next(row for row in candidates if str(row["model"]) == plan.selected.model_key)


def select_policy(
    rows: list[dict],
    policy: str,
    *,
    static_priors: dict[str, StaticModelPrior],
    weights: dict[str, float] | None = None,
    references: References = References(),
    constraints: Constraints = Constraints(),
    seed: int = 0,
    unavailable: set[str] | None = None,
) -> list[dict]:
    """Select one candidate per request without consulting held-out outcomes."""
    validate_observations(rows)
    validate_static_priors(rows, static_priors)
    unavailable = unavailable or set()
    rng = random.Random(seed)
    strongest = max(
        static_priors,
        key=lambda model: (static_priors[model].quality_prior, static_priors[model].priority, model),
    )
    cheapest = max(
        static_priors,
        key=lambda model: (static_priors[model].cost_prior, static_priors[model].priority, model),
    )
    selected: list[dict] = []

    for request_index, (_, candidates) in enumerate(group_by_request(rows)):
        available = [row for row in candidates if str(row["model"]) not in unavailable]
        if not available:
            continue
        if policy == "fixed_strongest":
            chosen = next((row for row in available if row["model"] == strongest), None)
            if chosen is None:
                chosen = max(available, key=lambda row: static_priors[str(row["model"])].quality_prior)
        elif policy == "fixed_cheapest":
            chosen = next((row for row in available if row["model"] == cheapest), None)
            if chosen is None:
                chosen = max(available, key=lambda row: static_priors[str(row["model"])].cost_prior)
        elif policy == "random":
            chosen = rng.choice(available)
        elif policy == "round_robin":
            chosen = available[request_index % len(available)]
        elif policy == "cost_first":
            chosen = min(available, key=lambda row: (float(row["profile_cost"]), str(row["model"])))
        elif policy == "latency_first":
            chosen = min(available, key=lambda row: (float(row["profile_latency_ms"]), str(row["model"])))
        elif policy == "static_weighted":
            chosen = max(
                available,
                key=lambda row: (
                    static_prior_score(static_priors[str(row["model"])], weights),
                    static_priors[str(row["model"])].priority,
                    str(row["model"]),
                ),
            )
        elif policy == "evalroute_feedback":
            chosen = _select_evalroute(available, static_priors, references, constraints, weights)
            if chosen is None:
                continue
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
    """Evaluate selections using post-invocation outcomes only."""
    if not chosen:
        return {
            "requests": 0, "mean_quality": 0.0, "mean_latency_ms": 0.0,
            "p95_latency_ms": 0.0, "mean_cost": 0.0, "total_cost": 0.0,
            "success_rate": 0.0, "constraint_violation_rate": 0.0,
            "utility": 0.0, "model_distribution": {},
        }
    n = len(chosen)
    qualities = [float(row["observed_quality"]) for row in chosen]
    latencies = [float(row["observed_latency_ms"]) for row in chosen]
    costs = [float(row["observed_cost"]) for row in chosen]
    successes = [float(row["observed_success"]) for row in chosen]
    violations = [
        (constraints.max_cost is not None and cost > constraints.max_cost)
        or (constraints.max_latency_ms is not None and latency > constraints.max_latency_ms)
        for cost, latency in zip(costs, latencies)
    ]
    utilities = [
        quality - 0.15 * (latency / 1000.0) - 10.0 * cost
        for quality, latency, cost in zip(qualities, latencies, costs)
    ]
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
        "utility": round(statistics.fmean(utilities), 4),
        "model_distribution": {model: round(count / n, 4) for model, count in sorted(counts.items())},
    }


def summarize_trials(trials: list[dict]) -> dict:
    summary: dict[str, dict[str, float]] = {}
    metrics = (
        "mean_quality", "mean_latency_ms", "p95_latency_ms", "mean_cost",
        "success_rate", "constraint_violation_rate", "utility",
    )
    for metric in metrics:
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


def _model_means(rows: list[dict], field: str) -> dict[str, float]:
    values: dict[str, list[float]] = defaultdict(list)
    for row in rows:
        values[str(row["model"])].append(float(row[field]))
    return {model: statistics.fmean(items) for model, items in values.items()}


def pareto_front(rows: list[dict]) -> list[str]:
    quality = _model_means(rows, "observed_quality")
    latency = _model_means(rows, "observed_latency_ms")
    cost = _model_means(rows, "observed_cost")
    metrics = {
        model: {"quality": quality[model], "latency": latency[model], "cost": cost[model]}
        for model in quality
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
            updated.update(changes)
        output.append(updated)
    return output


def run_suite(
    rows: list[dict],
    *,
    static_priors: dict[str, StaticModelPrior],
    repeats: int = 30,
    references: References = References(),
    constraints: Constraints = Constraints(),
) -> dict:
    validate_observations(rows)
    validate_static_priors(rows, static_priors)
    repeats = max(2, int(repeats))
    policies = [
        "fixed_strongest", "fixed_cheapest", "random", "round_robin",
        "cost_first", "latency_first", "static_weighted", "evalroute_feedback",
    ]
    baseline_trials = {
        policy: [
            aggregate(
                select_policy(
                    rows, policy, static_priors=static_priors, references=references,
                    constraints=constraints, seed=seed,
                ),
                constraints,
            )
            for seed in range(repeats if policy == "random" else 2)
        ]
        for policy in policies
    }
    sensitivity = {
        name: aggregate(
            select_policy(
                rows, "evalroute_feedback", static_priors=static_priors,
                weights=weights, references=references, constraints=constraints,
            ),
            constraints,
        )
        for name, weights in WEIGHT_PRESETS.items()
    }
    ablations = {
        f"without_{dimension}": aggregate(
            select_policy(
                rows, "evalroute_feedback", static_priors=static_priors,
                weights={**ROUTER_DEFAULT_WEIGHTS, dimension: 0.0},
                references=references, constraints=constraints,
            ),
            constraints,
        )
        for dimension in ROUTER_DEFAULT_WEIGHTS
    }
    models = sorted({str(row["model"]) for row in rows})
    target = models[len(models) // 2]
    affected = lambda row: str(row["model"]) == target
    latency_spike = transform(
        rows, affected,
        profile_latency_ms=references.latency_ms * 3,
        observed_latency_ms=references.latency_ms * 3,
    )
    price_spike = transform(
        rows, affected,
        profile_cost=references.cost_per_request * 3,
        observed_cost=references.cost_per_request * 3,
    )
    quality_drop = transform(rows, affected, profile_quality=0.3, observed_quality=0.3)
    stale_profile = transform(rows, affected, profile_age_days=90.0)
    low_sample = transform(rows, affected, profile_sample_count=1)

    def evaluated(dataset: list[dict], unavailable: set[str] | None = None) -> dict:
        return aggregate(
            select_policy(
                dataset, "evalroute_feedback", static_priors=static_priors,
                references=references, constraints=constraints, unavailable=unavailable,
            ),
            constraints,
        )

    return {
        "metadata": {
            "observation_rows": len(rows),
            "requests": len({row["request"] for row in rows}),
            "models": models,
            "repeats": repeats,
            "router_dimensions": list(ROUTER_DEFAULT_WEIGHTS),
            "router_default_weights": ROUTER_DEFAULT_WEIGHTS,
            "static_prior_models": sorted(static_priors),
            "selection_fields": "profile_* and immutable static priors only",
            "metric_fields": "observed_* only",
            "references": {
                "latency_ms": references.latency_ms,
                "cost_per_request": references.cost_per_request,
            },
            "constraints": {
                "max_cost": constraints.max_cost,
                "max_latency_ms": constraints.max_latency_ms,
            },
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
