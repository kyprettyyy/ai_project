"""Routing coordinator with evaluation-driven adaptive selection."""

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import ROUTING_STRATEGY_ADAPTIVE, ROUTING_STRATEGY_AUTO
from app.models.model import Model
from app.services.adaptive_routing_service import AdaptiveRoutingService
from app.routing.explainable_router import RoutingContext
from app.strategy.auto_routing_strategy import AutoRoutingStrategy
from app.strategy.cost_first_routing_strategy import CostFirstRoutingStrategy
from app.strategy.fixed_routing_strategy import FixedRoutingStrategy
from app.strategy.latency_first_routing_strategy import LatencyFirstRoutingStrategy
from app.strategy.routing_strategy import RoutingStrategy


class RoutingService:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db
        self.adaptive = AdaptiveRoutingService(db)
        self.last_ranked: list[tuple[Model, float, dict]] = []
        self.routing_strategies: list[RoutingStrategy] = [
            AutoRoutingStrategy(db), FixedRoutingStrategy(db),
            CostFirstRoutingStrategy(db), LatencyFirstRoutingStrategy(db),
        ]

    async def select_model(self, strategy_type: str | None, model_type: str, requested_model: str | None,
                           *, task_type: str = "general", weights: dict[str, float] | None = None,
                           trace_id: str | None = None, evaluation_run_id: str | None = None,
                           context: RoutingContext | None = None) -> Model | None:
        if strategy_type == ROUTING_STRATEGY_ADAPTIVE:
            self.last_ranked = await self.adaptive.rank_models(model_type, task_type, weights, context)
            if trace_id:
                await self.adaptive.persist_decision(
                    trace_id=trace_id, evaluation_run_id=evaluation_run_id, task_type=task_type,
                    requested_model=requested_model, weights=weights, ranked=self.last_ranked,
                )
            return self.last_ranked[0][0] if self.last_ranked else None
        strategy = self._get_strategy(strategy_type) or self._get_strategy(ROUTING_STRATEGY_AUTO)
        return await strategy.select_model(model_type, requested_model) if strategy else None

    async def get_fallback_models(self, strategy_type: str | None, model_type: str, requested_model: str | None,
                                  *, task_type: str = "general", weights: dict[str, float] | None = None,
                                  context: RoutingContext | None = None) -> list[Model]:
        if strategy_type == ROUTING_STRATEGY_ADAPTIVE:
            if not self.last_ranked:
                self.last_ranked = await self.adaptive.rank_models(model_type, task_type, weights, context)
            return [item[0] for item in self.last_ranked[1:]]
        strategy = self._get_strategy(strategy_type) or self._get_strategy(ROUTING_STRATEGY_AUTO)
        return await strategy.get_fallback_models(model_type, requested_model) if strategy else []

    @property
    def selected_score(self) -> float | None:
        return self.last_ranked[0][1] if self.last_ranked else None

    @property
    def selected_explanation(self) -> str | None:
        if not self.last_ranked:
            return None
        return self.last_ranked[0][2].get("explanation")

    @property
    def selected_estimated_cost(self) -> float | None:
        if not self.last_ranked:
            return None
        value = self.last_ranked[0][2].get("estimatedCost")
        return float(value) if value is not None else None

    def _get_strategy(self, strategy_type: str | None) -> RoutingStrategy | None:
        return next((strategy for strategy in self.routing_strategies if strategy.get_strategy_type() == strategy_type), None)
