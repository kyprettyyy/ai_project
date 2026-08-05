"""Dependency-free, constraint-aware and explainable model selection.

The database-facing service converts ORM entities into these domain objects. Keeping
the decision engine pure makes every score, rejection and tie-break reproducible in
unit tests and offline evaluation jobs.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Iterable


DEFAULT_WEIGHTS = {
    "quality": 0.30,
    "latency": 0.15,
    "cost": 0.15,
    "reliability": 0.15,
    "task": 0.10,
    "context": 0.075,
    "budget": 0.075,
}


@dataclass(slots=True)
class RoutingContext:
    task_type: str = "general"
    estimated_input_tokens: int = 0
    expected_output_tokens: int = 1024
    max_request_cost: Decimal | None = None
    budget_remaining: Decimal | None = None
    min_quality: float | None = None
    max_latency_ms: int | None = None
    min_success_rate: float | None = None
    required_capabilities: set[str] = field(default_factory=set)
    minimum_profile_samples: int = 20
    latency_reference_ms: int = 1000
    cost_reference: Decimal = Decimal("0.01")
    profile_half_life_days: float = 30.0
    quality_uncertainty_penalty: float = 0.05

    @property
    def required_tokens(self) -> int:
        return max(0, self.estimated_input_tokens) + max(0, self.expected_output_tokens)

    @property
    def effective_cost_limit(self) -> Decimal | None:
        positive = [
            value
            for value in (self.max_request_cost, self.budget_remaining)
            if value is not None and value >= 0
        ]
        return min(positive) if positive else None

    def snapshot(self) -> dict:
        return {
            "taskType": self.task_type,
            "estimatedInputTokens": self.estimated_input_tokens,
            "expectedOutputTokens": self.expected_output_tokens,
            "requiredTokens": self.required_tokens,
            "maxRequestCost": _decimal_or_none(self.max_request_cost),
            "budgetRemaining": _decimal_or_none(self.budget_remaining),
            "effectiveCostLimit": _decimal_or_none(self.effective_cost_limit),
            "minQuality": self.min_quality,
            "maxLatencyMs": self.max_latency_ms,
            "minSuccessRate": self.min_success_rate,
            "requiredCapabilities": sorted(self.required_capabilities),
            "minimumProfileSamples": self.minimum_profile_samples,
            "latencyReferenceMs": self.latency_reference_ms,
            "costReference": float(self.cost_reference),
            "profileHalfLifeDays": self.profile_half_life_days,
            "qualityUncertaintyPenalty": self.quality_uncertainty_penalty,
        }


@dataclass(slots=True)
class CandidateSignals:
    model_id: int
    model_key: str
    context_length: int
    input_price: Decimal
    output_price: Decimal
    avg_latency_ms: int
    live_success_rate: float
    priority: int = 100
    capabilities: set[str] = field(default_factory=set)
    quality_score: float = 0.5
    profile_latency_score: float = 0.5
    profile_cost_score: float = 0.5
    profile_reliability_score: float = 0.5
    sample_count: int = 0
    profile_version: int = 0
    profile_task_type: str | None = None
    profile_age_days: float = 0.0
    estimated_request_cost: Decimal | None = None
    quality_prior_score: float = 0.5
    latency_prior_score: float | None = None
    cost_prior_score: float | None = None
    reliability_prior_score: float | None = None

    def estimate_cost(self, context: RoutingContext) -> Decimal:
        if self.estimated_request_cost is not None:
            return max(Decimal("0"), self.estimated_request_cost).quantize(Decimal("0.000001"))
        input_cost = self.input_price * Decimal(context.estimated_input_tokens) / Decimal("1000")
        output_cost = self.output_price * Decimal(context.expected_output_tokens) / Decimal("1000")
        return (input_cost + output_cost).quantize(Decimal("0.000001"))


@dataclass(slots=True)
class CandidateDecision:
    model_id: int
    model_key: str
    eligible: bool
    rejection_reasons: list[str]
    estimated_cost: Decimal
    estimated_latency_ms: int
    profile_confidence: float
    scores: dict[str, float]
    weighted_score: float | None
    explanation: str
    priority: int
    profile_version: int
    sample_count: int

    def snapshot(self) -> dict:
        result = asdict(self)
        result["modelId"] = result.pop("model_id")
        result["modelKey"] = result.pop("model_key")
        result["rejectionReasons"] = result.pop("rejection_reasons")
        result["estimatedCost"] = _decimal_or_none(result.pop("estimated_cost"))
        result["estimatedLatencyMs"] = result.pop("estimated_latency_ms")
        result["profileConfidence"] = result.pop("profile_confidence")
        result["weightedScore"] = result.pop("weighted_score")
        result["profileVersion"] = result.pop("profile_version")
        result["sampleCount"] = result.pop("sample_count")
        return result


@dataclass(slots=True)
class RoutingPlan:
    context: RoutingContext
    weights: dict[str, float]
    candidates: list[CandidateDecision]

    @property
    def eligible(self) -> list[CandidateDecision]:
        return [item for item in self.candidates if item.eligible]

    @property
    def selected(self) -> CandidateDecision | None:
        return self.eligible[0] if self.eligible else None

    def snapshot(self) -> dict:
        return {
            "context": self.context.snapshot(),
            "weights": self.weights,
            "selectedModel": self.selected.model_key if self.selected else None,
            "candidates": [item.snapshot() for item in self.candidates],
        }


class ExplainableRouter:
    """Apply hard constraints first, then rank eligible candidates transparently."""

    def rank(
        self,
        candidates: Iterable[CandidateSignals],
        context: RoutingContext,
        weights: dict[str, float] | None = None,
    ) -> RoutingPlan:
        items = list(candidates)
        normalized_weights = normalize_weights(weights)
        if not items:
            return RoutingPlan(context=context, weights=normalized_weights, candidates=[])

        estimates = {item.model_id: item.estimate_cost(context) for item in items}
        decisions: list[CandidateDecision] = []

        for item in items:
            estimated_cost = estimates[item.model_id]
            sample_confidence = min(1.0, max(0, item.sample_count) / max(1, context.minimum_profile_samples))
            age = max(0.0, float(item.profile_age_days))
            half_life = max(0.000001, float(context.profile_half_life_days))
            freshness = math.exp2(-age / half_life)
            confidence = sample_confidence * freshness
            quality = _blend(item.quality_score, item.quality_prior_score, confidence)
            quality = _clamp01(
                quality - max(0.0, context.quality_uncertainty_penalty) * (1.0 - confidence)
            )
            live_latency_score = _inverse_score(
                max(0, item.avg_latency_ms), max(1, context.latency_reference_ms)
            )
            latency = _blend(
                item.profile_latency_score,
                live_latency_score if item.latency_prior_score is None else item.latency_prior_score,
                confidence,
            )
            live_cost_score = _inverse_score(
                float(estimated_cost), max(0.000001, float(context.cost_reference))
            )
            cost = _blend(
                item.profile_cost_score,
                live_cost_score if item.cost_prior_score is None else item.cost_prior_score,
                confidence,
            )
            live_reliability = _clamp01(item.live_success_rate)
            reliability = _blend(
                item.profile_reliability_score,
                live_reliability if item.reliability_prior_score is None else item.reliability_prior_score,
                confidence,
            )
            task = self._task_score(item, context)
            required_tokens = max(1, context.required_tokens)
            context_score = _clamp01(item.context_length / (required_tokens * 4))
            limit = context.effective_cost_limit
            budget = _clamp01(1.0 - float(estimated_cost / limit)) if limit and limit > 0 else 0.5
            scores = {
                "quality": quality,
                "latency": latency,
                "cost": cost,
                "reliability": reliability,
                "task": task,
                "context": context_score,
                "budget": budget,
            }
            rejections = self._rejections(item, context, estimated_cost, quality, live_reliability)
            weighted = None if rejections else sum(scores[key] * normalized_weights[key] for key in DEFAULT_WEIGHTS)
            explanation = self._explain(item, context, scores, normalized_weights, rejections, estimated_cost, confidence)
            decisions.append(
                CandidateDecision(
                    model_id=item.model_id,
                    model_key=item.model_key,
                    eligible=not rejections,
                    rejection_reasons=rejections,
                    estimated_cost=estimated_cost,
                    estimated_latency_ms=max(0, item.avg_latency_ms),
                    profile_confidence=round(confidence, 4),
                    scores={key: round(value, 6) for key, value in scores.items()},
                    weighted_score=round(weighted, 6) if weighted is not None else None,
                    explanation=explanation,
                    priority=item.priority,
                    profile_version=item.profile_version,
                    sample_count=item.sample_count,
                )
            )

        decisions.sort(
            key=lambda value: (
                not value.eligible,
                -(value.weighted_score or 0.0),
                -value.priority,
                value.model_key,
            )
        )
        return RoutingPlan(context=context, weights=normalized_weights, candidates=decisions)

    @staticmethod
    def _task_score(candidate: CandidateSignals, context: RoutingContext) -> float:
        if candidate.profile_task_type == context.task_type:
            return 1.0
        if candidate.profile_task_type == "general":
            return 0.7
        if context.task_type in candidate.capabilities:
            return 0.85
        return 0.5

    @staticmethod
    def _rejections(
        candidate: CandidateSignals,
        context: RoutingContext,
        estimated_cost: Decimal,
        quality: float,
        live_reliability: float,
    ) -> list[str]:
        reasons: list[str] = []
        if candidate.context_length < context.required_tokens:
            reasons.append(
                f"context_length {candidate.context_length} < required_tokens {context.required_tokens}"
            )
        if context.effective_cost_limit is not None and estimated_cost > context.effective_cost_limit:
            reasons.append(
                f"estimated_cost {estimated_cost} > cost_limit {context.effective_cost_limit}"
            )
        if context.min_quality is not None and quality < context.min_quality:
            reasons.append(f"quality {quality:.4f} < min_quality {context.min_quality:.4f}")
        if context.max_latency_ms is not None and candidate.avg_latency_ms > context.max_latency_ms:
            reasons.append(
                f"avg_latency_ms {candidate.avg_latency_ms} > max_latency_ms {context.max_latency_ms}"
            )
        if context.min_success_rate is not None and live_reliability < context.min_success_rate:
            reasons.append(
                f"success_rate {live_reliability:.4f} < min_success_rate {context.min_success_rate:.4f}"
            )
        missing = context.required_capabilities - candidate.capabilities
        if missing:
            reasons.append(f"missing_capabilities: {', '.join(sorted(missing))}")
        return reasons

    @staticmethod
    def _explain(
        candidate: CandidateSignals,
        context: RoutingContext,
        scores: dict[str, float],
        weights: dict[str, float],
        rejections: list[str],
        estimated_cost: Decimal,
        confidence: float,
    ) -> str:
        if rejections:
            return f"淘汰 {candidate.model_key}：" + "；".join(rejections)
        contributions = sorted(
            ((key, scores[key] * weights[key]) for key in DEFAULT_WEIGHTS),
            key=lambda pair: pair[1],
            reverse=True,
        )
        top = "、".join(f"{name}={value:.4f}" for name, value in contributions[:3])
        return (
            f"保留 {candidate.model_key}：主要贡献 {top}；预计成本 {estimated_cost}，"
            f"上下文 {context.required_tokens}/{candidate.context_length} tokens，"
            f"画像置信度 {confidence:.0%}。"
        )


def normalize_weights(overrides: dict[str, float] | None) -> dict[str, float]:
    if not overrides:
        return dict(DEFAULT_WEIGHTS)
    values = {**DEFAULT_WEIGHTS, **(overrides or {})}
    values = {
        key: _finite_non_negative(values.get(key, 0.0))
        for key in DEFAULT_WEIGHTS
    }
    total = sum(values.values())
    if total <= 0:
        return dict(DEFAULT_WEIGHTS)
    return {key: value / total for key, value in values.items()}


def parse_capabilities(value: str | Iterable[str] | None) -> set[str]:
    if value is None:
        return set()
    if not isinstance(value, str):
        return {str(item).strip().lower() for item in value if str(item).strip()}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        parsed = value.split(",")
    if isinstance(parsed, dict):
        parsed = [key for key, enabled in parsed.items() if enabled]
    if not isinstance(parsed, list):
        parsed = [parsed]
    return {str(item).strip().lower() for item in parsed if str(item).strip()}


def estimate_message_tokens(contents: Iterable[str]) -> int:
    """Conservative dependency-free estimate for routing, not provider billing."""
    total_characters = sum(len(content or "") for content in contents)
    return 0 if total_characters == 0 else max(1, (total_characters + 2) // 3)


def _blend(profile_value: float, live_or_prior_value: float, confidence: float) -> float:
    return _clamp01(_clamp01(profile_value) * confidence + _clamp01(live_or_prior_value) * (1.0 - confidence))


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def _inverse_score(value: float, reference: float) -> float:
    """Map a non-negative measurement to (0, 1] using a fixed reference.

    Unlike candidate-relative min-max scaling, this score does not change when an
    unrelated model is added to or removed from the candidate set.
    """
    safe_value = max(0.0, float(value))
    safe_reference = max(0.000001, float(reference))
    return 1.0 / (1.0 + safe_value / safe_reference)


def _finite_non_negative(value: object) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, number) if math.isfinite(number) else 0.0


def _decimal_or_none(value: Decimal | None) -> float | None:
    return float(value) if value is not None else None
