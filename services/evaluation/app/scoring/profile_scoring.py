"""Dependency-free scoring and profile aggregation for the evaluation feedback loop."""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime


def normalize_score(value: object, scale: float) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if scale <= 0 or not math.isfinite(number):
        return None
    return max(0.0, min(1.0, number / scale))


def parse_ai_scores(value: object) -> tuple[float | None, float | None]:
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return None, None
    if not isinstance(value, dict):
        return None, None
    judge_raw = value.get("averageRating")
    judge = normalize_score(judge_raw if judge_raw is not None else value.get("score"), 10.0)
    correctness_raw = value.get("correctness")
    if correctness_raw is None:
        correctness_raw = value.get("correctnessScore")
    try:
        correctness_number = float(correctness_raw) if correctness_raw is not None else None
    except (TypeError, ValueError):
        correctness_number = None
    if correctness_number is None:
        correctness = None
    elif correctness_number <= 1:
        correctness = normalize_score(correctness_number, 1.0)
    elif correctness_number <= 10:
        correctness = normalize_score(correctness_number, 10.0)
    else:
        correctness = normalize_score(correctness_number, 100.0)
    return judge, correctness


def combined_quality(row: dict) -> dict[str, float | None]:
    human = normalize_score(row.get("user_rating"), 5.0)
    judge, correctness = parse_ai_scores(row.get("ai_score"))
    components = {
        "human": (human, 0.35),
        "judge": (judge, 0.40),
        "correctness": (correctness, 0.25),
    }
    available = [(value, weight) for value, weight in components.values() if value is not None]
    total_weight = sum(weight for _, weight in available)
    combined = sum(value * weight for value, weight in available) / total_weight if total_weight else None
    return {
        "human": human,
        "judge": judge,
        "correctness": correctness,
        "combined": combined,
    }


def task_type_from_config(value: object) -> str:
    if isinstance(value, str):
        try:
            value = json.loads(value or "{}")
        except (TypeError, json.JSONDecodeError):
            return "general"
    if not isinstance(value, dict):
        return "general"
    task_type = str(value.get("taskType") or value.get("task_type") or "general").strip()
    return task_type or "general"


def build_profiles(
    observations: list[dict],
    evaluation_run_id: str,
    evaluated_at: datetime | None = None,
    *,
    latency_reference_ms: float = 1000.0,
    cost_reference: float = 0.01,
) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in observations:
        model = str(row.get("model_name") or "").strip()
        if not model:
            continue
        groups[(model, task_type_from_config(row.get("task_config")))].append(row)

    aggregates = []
    for (model, task_type), items in groups.items():
        quality_values = [combined_quality(item)["combined"] for item in items
                          if (item.get("output_text") or "").strip()
                          and combined_quality(item)["combined"] is not None]
        successes = [item for item in items if (item.get("output_text") or "").strip() and not item.get("error_message")]
        latencies = [float(item["latency"]) for item in items if item.get("latency") is not None and float(item["latency"]) > 0]
        costs = [float(item["cost"]) for item in items if item.get("cost") is not None
                 and item.get("cost_currency") in ("CNY", "USD") and float(item["cost"]) >= 0]
        currencies = {item["cost_currency"] for item in items if item.get("cost") is not None and item.get("cost_currency") in ("CNY", "USD")}
        complete_cost = len(costs) == len(items) and len(currencies) == 1
        aggregates.append({"model":model,"task_type":task_type,"sample_count":len(items),
            "quality":sum(quality_values)/len(quality_values) if quality_values else None,
            "latency":sum(latencies)/len(latencies) if latencies else None,
            "cost":sum(costs)/len(costs) if complete_cost else None,
            "currency":next(iter(currencies)) if len(currencies)==1 else None,
            "reliability":len(successes)/len(items),
            "coverage":{"ratedSamples":len(quality_values),"emptySamples":len(items)-len(successes),
                        "latencySamples":len(latencies),"costSamples":len(costs),
                        "costComplete":complete_cost,"costCurrency":next(iter(currencies)) if len(currencies)==1 else None}})
    # Compare costs only within the same task and currency. Unknown cost is neutral,
    # never interpreted as free or as maximum cost efficiency.
    timestamp=(evaluated_at or datetime.utcnow()).isoformat()
    profiles=[]
    for row in aggregates:
        peers=[r for r in aggregates if r["task_type"]==row["task_type"]]
        cost_peers=[r for r in peers if r["cost"] is not None and r["currency"]==row["currency"]]
        row["coverage"]["costComparable"]=row["cost"] is not None and len(cost_peers)>=2
        profiles.append({"model":row["model"],"task_type":row["task_type"],
            "quality_score":round(row["quality"],4) if row["quality"] is not None else .5,
            "latency_score":round(inverse_reference_score(row["latency"], latency_reference_ms),4) if row["latency"] is not None else .5,
            "cost_score":round(inverse_reference_score(row["cost"], cost_reference),4) if row["coverage"]["costComparable"] else .5,
            "reliability_score":round(row["reliability"],4),"sample_count":row["sample_count"],
            "coverage":row["coverage"],"evaluation_run_id":evaluation_run_id,"evaluated_at":timestamp})
    return profiles

def inverse_reference_score(value: float, reference: float) -> float:
    """Return a stable higher-is-better score using a fixed positive reference."""
    safe_value = max(0.0, float(value))
    safe_reference = max(0.000001, float(reference))
    return 1.0 / (1.0 + safe_value / safe_reference)
