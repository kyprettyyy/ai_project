"""Internal read-only API for routing decision audit."""

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.db.session import get_db_session
from app.models.routing_decision import RoutingDecision

router = APIRouter(prefix="/internal/routing-decisions", tags=["routing-audit"])


def verify(token: str | None) -> None:
    if token != get_settings().internal_service_token:
        raise HTTPException(status_code=401, detail="invalid internal service token")


@router.get("")
async def list_decisions(limit: int = Query(default=50, ge=1, le=200),
                         x_internal_token: str | None = Header(default=None),
                         db: AsyncSession = Depends(get_db_session)):
    verify(x_internal_token)
    items = list((await db.scalars(
        select(RoutingDecision).order_by(RoutingDecision.created_at.desc()).limit(limit)
    )).all())
    return [{
        "traceId": item.trace_id, "evaluationRunId": item.evaluation_run_id,
        "taskType": item.task_type, "strategy": item.strategy,
        "requestedModel": item.requested_model, "selectedModel": item.selected_model_key,
        "finalScore": float(item.final_score) if item.final_score is not None else None,
        "weights": {"quality": float(item.quality_weight), "latency": float(item.latency_weight),
                    "cost": float(item.cost_weight), "reliability": float(item.reliability_weight)},
        "candidates": item.candidate_snapshot, "fallbackOrder": item.fallback_order,
        "createdAt": item.created_at.isoformat(),
    } for item in items]


@router.get("/{trace_id}")
async def get_decision(trace_id: str, x_internal_token: str | None = Header(default=None),
                       db: AsyncSession = Depends(get_db_session)):
    verify(x_internal_token)
    item = await db.scalar(select(RoutingDecision).where(RoutingDecision.trace_id == trace_id))
    if item is None:
        raise HTTPException(status_code=404, detail="routing decision not found")
    return {"traceId": item.trace_id, "selectedModel": item.selected_model_key,
            "taskType": item.task_type, "candidates": item.candidate_snapshot,
            "fallbackOrder": item.fallback_order}
