"""Evaluation-driven, task-aware, multi-objective model routing."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import HEALTH_STATUS_DEGRADED, HEALTH_STATUS_HEALTHY, HEALTH_STATUS_UNKNOWN, MODEL_STATUS_ACTIVE
from app.models.model import Model
from app.models.model_capability_profile import ModelCapabilityProfile
from app.models.routing_decision import RoutingDecision


DEFAULT_WEIGHTS = {"quality": 0.45, "latency": 0.20, "cost": 0.20, "reliability": 0.15}


class AdaptiveRoutingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def rank_models(self, model_type: str, task_type: str, weights: dict[str, float] | None) -> list[tuple[Model, float, dict]]:
        models = list((await self.db.scalars(select(Model).where(
            Model.is_delete == 0,
            Model.status == MODEL_STATUS_ACTIVE,
            Model.health_status.in_([HEALTH_STATUS_HEALTHY, HEALTH_STATUS_DEGRADED, HEALTH_STATUS_UNKNOWN]),
            Model.model_type == model_type,
        ))).all())
        if not models:
            return []

        model_ids = [model.id for model in models]
        profiles = list((await self.db.scalars(select(ModelCapabilityProfile).where(
            ModelCapabilityProfile.model_id.in_(model_ids),
            ModelCapabilityProfile.task_type.in_([task_type, "general"]),
        ))).all())
        exact = {(p.model_id, p.task_type): p for p in profiles}
        normalized_weights = self.normalize_weights(weights)
        max_latency = max([model.avg_latency or 0 for model in models] + [1])
        max_cost = max([float(model.input_price + model.output_price) for model in models] + [0.000001])
        ranked: list[tuple[Model, float, dict]] = []
        for model in models:
            profile = exact.get((model.id, task_type)) or exact.get((model.id, "general"))
            metrics = {
                "quality": float(profile.quality_score) if profile else 0.5,
                "latency": float(profile.latency_score) if profile else max(0.0, 1.0 - float(model.avg_latency or 0) / max_latency),
                "cost": float(profile.cost_score) if profile else max(0.0, 1.0 - float(model.input_price + model.output_price) / max_cost),
                "reliability": float(profile.reliability_score) if profile else float(model.success_rate or 0) / 100.0,
                "sampleCount": profile.sample_count if profile else 0,
                "profileVersion": profile.profile_version if profile else 0,
            }
            score = sum(metrics[key] * normalized_weights[key] for key in normalized_weights)
            ranked.append((model, score, metrics))
        return sorted(ranked, key=lambda item: (-item[1], item[0].priority, item[0].id))

    async def persist_decision(self, *, trace_id: str, evaluation_run_id: str | None, task_type: str,
                               requested_model: str | None, weights: dict[str, float] | None,
                               ranked: list[tuple[Model, float, dict]]) -> RoutingDecision | None:
        if not ranked:
            return None
        final_weights = self.normalize_weights(weights)
        selected, score, _ = ranked[0]
        snapshot = [{"model": model.model_key, "score": round(value, 6), **metrics} for model, value, metrics in ranked]
        entity = RoutingDecision(
            trace_id=trace_id,
            evaluation_run_id=evaluation_run_id,
            task_type=task_type,
            strategy="adaptive",
            requested_model=requested_model,
            selected_model_id=selected.id,
            selected_model_key=selected.model_key,
            quality_weight=Decimal(str(final_weights["quality"])),
            latency_weight=Decimal(str(final_weights["latency"])),
            cost_weight=Decimal(str(final_weights["cost"])),
            reliability_weight=Decimal(str(final_weights["reliability"])),
            final_score=Decimal(str(round(score, 6))),
            candidate_snapshot=snapshot,
            fallback_order=[model.model_key for model, _, _ in ranked[1:]],
        )
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)
        return entity

    @staticmethod
    def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
        values = {**DEFAULT_WEIGHTS, **(weights or {})}
        values = {key: max(0.0, float(values.get(key, 0.0))) for key in DEFAULT_WEIGHTS}
        total = sum(values.values()) or 1.0
        return {key: value / total for key, value in values.items()}
