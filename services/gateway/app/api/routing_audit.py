"""Internal read-only API for routing explanations and observed outcomes."""

from __future__ import annotations

from collections import defaultdict

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.request_log import RequestLog
from app.models.routing_decision import RoutingDecision

router = APIRouter(prefix="/internal/routing-decisions", tags=["routing-audit"])


def verify(token: str | None) -> None:
    if token != get_settings().internal_service_token:
        raise HTTPException(status_code=401, detail="invalid internal service token")


def _snapshot_parts(item: RoutingDecision) -> tuple[dict, list[dict], dict[str, float]]:
    snapshot = item.candidate_snapshot or {}
    if isinstance(snapshot, dict):
        return (
            snapshot.get("context") or {},
            snapshot.get("candidates") or [],
            snapshot.get("weights") or {},
        )
    return {}, snapshot if isinstance(snapshot, list) else [], {}


def _selected_candidate(item: RoutingDecision) -> dict | None:
    _, candidates, _ = _snapshot_parts(item)
    return next(
        (candidate for candidate in candidates if candidate.get("modelKey") == item.selected_model_key),
        None,
    )


def _decision_payload(item: RoutingDecision) -> dict:
    context, candidates, extended_weights = _snapshot_parts(item)
    selected = _selected_candidate(item)
    legacy_weights = {
        "quality": float(item.quality_weight),
        "latency": float(item.latency_weight),
        "cost": float(item.cost_weight),
        "reliability": float(item.reliability_weight),
    }
    return {
        "traceId": item.trace_id,
        "evaluationRunId": item.evaluation_run_id,
        "taskType": item.task_type,
        "strategy": item.strategy,
        "requestedModel": item.requested_model,
        "selectedModel": item.selected_model_key,
        "selectionExplanation": selected.get("explanation") if selected else "没有候选模型满足硬约束",
        "finalScore": float(item.final_score) if item.final_score is not None else None,
        "weights": extended_weights or legacy_weights,
        "context": context,
        "candidates": candidates,
        "fallbackOrder": item.fallback_order,
        "createdAt": item.created_at.isoformat(),
    }


def _outcome_payload(logs: list[RequestLog], selected: dict | None) -> dict | None:
    if not logs:
        return None
    successful = next((log for log in reversed(logs) if log.status == "success"), None)
    actual = successful or logs[-1]
    estimated_cost = selected.get("estimatedCost") if selected else None
    estimated_latency = selected.get("estimatedLatencyMs") if selected else None
    actual_cost = float(actual.cost or 0)
    actual_latency = actual.duration or 0
    return {
        "status": actual.status,
        "actualModel": actual.model_name,
        "actualCost": actual_cost,
        "actualLatencyMs": actual_latency,
        "fallback": bool(actual.is_fallback),
        "attempts": len(logs),
        "estimatedCost": estimated_cost,
        "estimatedLatencyMs": estimated_latency,
        "costDelta": round(actual_cost - float(estimated_cost), 6) if estimated_cost is not None else None,
        "latencyDeltaMs": actual_latency - int(estimated_latency) if estimated_latency is not None else None,
    }


@router.get("")
async def list_decisions(
    limit: int = Query(default=50, ge=1, le=200),
    x_internal_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
):
    verify(x_internal_token)
    items = list((await db.scalars(
        select(RoutingDecision).order_by(RoutingDecision.created_at.desc()).limit(limit)
    )).all())
    return [_decision_payload(item) for item in items]


@router.get("/effects")
async def routing_effects(
    limit: int = Query(default=500, ge=1, le=5000),
    task_type: str | None = Query(default=None),
    x_internal_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
):
    """Aggregate observed cost/latency/success by evaluation/profile generation."""
    verify(x_internal_token)
    stmt = select(RoutingDecision).order_by(RoutingDecision.created_at.desc()).limit(limit)
    if task_type:
        stmt = select(RoutingDecision).where(RoutingDecision.task_type == task_type).order_by(
            RoutingDecision.created_at.desc()
        ).limit(limit)
    decisions = list((await db.scalars(stmt)).all())
    trace_ids = [item.trace_id for item in decisions]
    logs = list((await db.scalars(select(RequestLog).where(RequestLog.trace_id.in_(trace_ids)))).all()) if trace_ids else []
    logs_by_trace: dict[str, list[RequestLog]] = defaultdict(list)
    for log in logs:
        if log.trace_id:
            logs_by_trace[log.trace_id].append(log)

    groups: dict[str, dict] = {}
    for decision in decisions:
        selected = _selected_candidate(decision)
        profile_version = selected.get("profileVersion", 0) if selected else 0
        group_key = decision.evaluation_run_id or f"profile-v{profile_version}"
        bucket = groups.setdefault(group_key, {
            "evaluationRunId": decision.evaluation_run_id,
            "profileVersion": profile_version,
            "requests": 0,
            "successes": 0,
            "fallbacks": 0,
            "totalCost": 0.0,
            "totalLatencyMs": 0,
            "models": defaultdict(int),
        })
        outcome = _outcome_payload(logs_by_trace.get(decision.trace_id, []), selected)
        if not outcome:
            continue
        bucket["requests"] += 1
        bucket["successes"] += int(outcome["status"] == "success")
        bucket["fallbacks"] += int(outcome["fallback"])
        bucket["totalCost"] += outcome["actualCost"]
        bucket["totalLatencyMs"] += outcome["actualLatencyMs"]
        bucket["models"][outcome["actualModel"]] += 1

    result = []
    for key, bucket in groups.items():
        requests = bucket.pop("requests")
        successes = bucket.pop("successes")
        fallbacks = bucket.pop("fallbacks")
        total_cost = bucket.pop("totalCost")
        total_latency = bucket.pop("totalLatencyMs")
        models = dict(bucket.pop("models"))
        result.append({
            "generation": key,
            **bucket,
            "requests": requests,
            "successRate": round(successes / requests, 4) if requests else None,
            "fallbackRate": round(fallbacks / requests, 4) if requests else None,
            "averageCost": round(total_cost / requests, 6) if requests else None,
            "averageLatencyMs": round(total_latency / requests, 2) if requests else None,
            "selectedModels": models,
        })
    return result


@router.get("/{trace_id}")
async def get_decision(
    trace_id: str,
    x_internal_token: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db_session),
):
    verify(x_internal_token)
    item = await db.scalar(select(RoutingDecision).where(RoutingDecision.trace_id == trace_id))
    if item is None:
        raise HTTPException(status_code=404, detail="routing decision not found")
    logs = list((await db.scalars(
        select(RequestLog).where(RequestLog.trace_id == trace_id).order_by(RequestLog.create_time.asc())
    )).all())
    payload = _decision_payload(item)
    payload["outcome"] = _outcome_payload(logs, _selected_candidate(item))
    return payload
