"""Dependency-free scoring and profile aggregation for the evaluation feedback loop."""

from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime


def normalize_score(value: object, scale: float) -> float | None:
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    if scale <= 0:
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
    judge = normalize_score(value.get("averageRating") or value.get("score"), 10.0)
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
) -> list[dict]:
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for row in observations:
        model = str(row.get("model_name") or "").strip()
        if not model:
            continue
        groups[(model, task_type_from_config(row.get("task_config")))].append(row)

    aggregates: list[dict] = []
    for (model, task_type), items in groups.items():
        quality_values = [
            score["combined"]
            for score in (combined_quality(item) for item in items)
            if score["combined"] is not None
        ]
        successes = [item for item in items if item.get("output_text") and not item.get("error_message")]
        aggregates.append({
            "model": model,
            "task_type": task_type,
            "sample_count": len(items),
            "quality": sum(quality_values) / len(quality_values) if quality_values else 0.5,
            "latency": sum(max(0.0, float(item.get("latency") or 0)) for item in items) / len(items),
            "cost": sum(max(0.0, float(item.get("cost") or 0)) for item in items) / len(items),
            "reliability": len(successes) / len(items),
        })

    max_latency = max((row["latency"] for row in aggregates), default=1.0) or 1.0
    max_cost = max((row["cost"] for row in aggregates), default=0.000001) or 0.000001
    timestamp = (evaluated_at or datetime.utcnow()).isoformat()
    return [{
        "model": row["model"],
        "task_type": row["task_type"],
        "quality_score": round(float(row["quality"]), 4),
        "latency_score": round(max(0.0, 1.0 - float(row["latency"]) / max_latency), 4),
        "cost_score": round(max(0.0, 1.0 - float(row["cost"]) / max_cost), 4),
        "reliability_score": round(float(row["reliability"]), 4),
        "sample_count": int(row["sample_count"]),
        "evaluation_run_id": evaluation_run_id,
        "evaluated_at": timestamp,
    } for row in aggregates]
