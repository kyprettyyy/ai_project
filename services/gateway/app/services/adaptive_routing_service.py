"""Database adapter for the explainable constraint-aware routing domain."""

from __future__ import annotations

from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import HEALTH_STATUS_DEGRADED, HEALTH_STATUS_HEALTHY, HEALTH_STATUS_UNKNOWN, MODEL_STATUS_ACTIVE
from app.models.model import Model
from app.models.model_capability_profile import ModelCapabilityProfile
from app.models.routing_decision import RoutingDecision
from app.routing.explainable_router import (
    DEFAULT_WEIGHTS,
    CandidateSignals,
    ExplainableRouter,
    RoutingContext,
    RoutingPlan,
    normalize_weights,
    parse_capabilities,
)


class AdaptiveRoutingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.engine = ExplainableRouter()
        self.last_plan: RoutingPlan | None = None

    async def rank_models(
        self,
        model_type: str,
        task_type: str,
        weights: dict[str, float] | None,
        context: RoutingContext | None = None,
    ) -> list[tuple[Model, float, dict]]:
        models = list((await self.db.scalars(select(Model).where(
            Model.is_delete == 0,
            Model.status == MODEL_STATUS_ACTIVE,
            Model.health_status.in_([HEALTH_STATUS_HEALTHY, HEALTH_STATUS_DEGRADED, HEALTH_STATUS_UNKNOWN]),
            Model.model_type == model_type,
        ))).all())
        routing_context = context or RoutingContext(task_type=task_type)
        routing_context.task_type = task_type
        if not models:
            self.last_plan = self.engine.rank([], routing_context, weights)
            return []

        model_ids = [model.id for model in models]
        profiles = list((await self.db.scalars(select(ModelCapabilityProfile).where(
            ModelCapabilityProfile.model_id.in_(model_ids),
            ModelCapabilityProfile.task_type.in_([task_type, "general"]),
        ))).all())
        exact = {(profile.model_id, profile.task_type): profile for profile in profiles}
        signals: list[CandidateSignals] = []
        model_by_id = {model.id: model for model in models}
        for model in models:
            profile = exact.get((model.id, task_type)) or exact.get((model.id, "general"))
            signals.append(CandidateSignals(
                model_id=model.id,
                model_key=model.model_key,
                context_length=max(0, model.context_length or 0),
                input_price=Decimal(model.input_price or 0),
                output_price=Decimal(model.output_price or 0),
                avg_latency_ms=max(0, model.avg_latency or 0),
                live_success_rate=float(model.success_rate or 0) / 100.0,
                priority=model.priority or 0,
                capabilities=parse_capabilities(model.capabilities),
                quality_score=float(profile.quality_score) if profile else 0.5,
                profile_latency_score=float(profile.latency_score) if profile else 0.5,
                profile_cost_score=float(profile.cost_score) if profile else 0.5,
                profile_reliability_score=float(profile.reliability_score) if profile else 0.5,
                sample_count=profile.sample_count if profile else 0,
                profile_version=profile.profile_version if profile else 0,
                profile_task_type=profile.task_type if profile else None,
            ))

        self.last_plan = self.engine.rank(signals, routing_context, weights)
        return [
            (
                model_by_id[decision.model_id],
                float(decision.weighted_score or 0),
                decision.snapshot(),
            )
            for decision in self.last_plan.eligible
        ]

    async def persist_decision(
        self,
        *,
        trace_id: str,
        evaluation_run_id: str | None,
        task_type: str,
        requested_model: str | None,
        weights: dict[str, float] | None,
        ranked: list[tuple[Model, float, dict]],
    ) -> RoutingDecision:
        final_weights = self.last_plan.weights if self.last_plan else normalize_weights(weights)
        selected = ranked[0][0] if ranked else None
        score = ranked[0][1] if ranked else None
        snapshot = self.last_plan.snapshot() if self.last_plan else {
            "context": RoutingContext(task_type=task_type).snapshot(),
            "weights": final_weights,
            "selectedModel": selected.model_key if selected else None,
            "candidates": [metrics for _, _, metrics in ranked],
        }
        entity = RoutingDecision(
            trace_id=trace_id,
            evaluation_run_id=evaluation_run_id,
            task_type=task_type,
            strategy="adaptive_explainable_v2",
            requested_model=requested_model,
            selected_model_id=selected.id if selected else None,
            selected_model_key=selected.model_key if selected else None,
            quality_weight=Decimal(str(final_weights["quality"])),
            latency_weight=Decimal(str(final_weights["latency"])),
            cost_weight=Decimal(str(final_weights["cost"])),
            reliability_weight=Decimal(str(final_weights["reliability"])),
            final_score=Decimal(str(round(score, 6))) if score is not None else None,
            candidate_snapshot=snapshot,
            fallback_order=[model.model_key for model, _, _ in ranked[1:]],
        )
        self.db.add(entity)
        await self.db.commit()
        await self.db.refresh(entity)
        return entity

    @staticmethod
    def normalize_weights(weights: dict[str, float] | None) -> dict[str, float]:
        return normalize_weights(weights)
