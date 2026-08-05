from __future__ import annotations

import sys
import unittest
from dataclasses import replace
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "gateway"))

from app.routing.explainable_router import (
    DEFAULT_WEIGHTS,
    CandidateSignals,
    ExplainableRouter,
    RoutingContext,
    estimate_message_tokens,
    normalize_weights,
    parse_capabilities,
)


def candidate(
    model_id: int,
    key: str,
    *,
    quality: float,
    input_price: str,
    output_price: str,
    context_length: int = 32768,
    latency: int = 500,
    success: float = 0.99,
    capabilities: set[str] | None = None,
    sample_count: int = 100,
    profile_age_days: float = 0,
    priority: int = 100,
) -> CandidateSignals:
    return CandidateSignals(
        model_id=model_id,
        model_key=key,
        context_length=context_length,
        input_price=Decimal(input_price),
        output_price=Decimal(output_price),
        avg_latency_ms=latency,
        live_success_rate=success,
        capabilities=capabilities or {"chat"},
        priority=priority,
        quality_score=quality,
        profile_latency_score=max(0, 1 - latency / 2000),
        profile_cost_score=0.5,
        profile_reliability_score=success,
        sample_count=sample_count,
        profile_version=3,
        profile_task_type="code",
        profile_age_days=profile_age_days,
    )


class ExplainableRoutingTest(unittest.TestCase):
    def setUp(self) -> None:
        self.router = ExplainableRouter()

    def test_budget_and_context_are_hard_constraints(self) -> None:
        plan = self.router.rank(
            [
                candidate(1, "large-expensive", quality=0.98, input_price="1", output_price="1"),
                candidate(
                    2,
                    "small-context",
                    quality=0.8,
                    input_price="0.001",
                    output_price="0.001",
                    context_length=100,
                ),
                candidate(3, "eligible", quality=0.75, input_price="0.001", output_price="0.002"),
            ],
            RoutingContext(
                task_type="code",
                estimated_input_tokens=1000,
                expected_output_tokens=1000,
                max_request_cost=Decimal("0.01"),
            ),
        )
        self.assertEqual(plan.selected.model_key, "eligible")
        rejected = {item.model_key: item.rejection_reasons for item in plan.candidates if not item.eligible}
        self.assertTrue(any("estimated_cost" in reason for reason in rejected["large-expensive"]))
        self.assertTrue(any("context_length" in reason for reason in rejected["small-context"]))

    def test_required_capability_is_enforced(self) -> None:
        plan = self.router.rank(
            [candidate(1, "plain", quality=0.9, input_price="0", output_price="0")],
            RoutingContext(task_type="vision", required_capabilities={"vision"}),
        )
        self.assertIsNone(plan.selected)
        self.assertIn("missing_capabilities: vision", plan.candidates[0].rejection_reasons)

    def test_explanation_contains_contributions_cost_and_confidence(self) -> None:
        plan = self.router.rank(
            [candidate(1, "explained", quality=0.9, input_price="0.001", output_price="0.002")],
            RoutingContext(task_type="code", estimated_input_tokens=100, expected_output_tokens=100),
        )
        explanation = plan.selected.explanation
        self.assertIn("主要贡献", explanation)
        self.assertIn("预计成本", explanation)
        self.assertIn("画像置信度", explanation)

    def test_empty_candidate_set_has_no_selection(self) -> None:
        plan = self.router.rank([], RoutingContext())
        self.assertIsNone(plan.selected)
        self.assertEqual(plan.candidates, [])

    def test_single_candidate_is_selected(self) -> None:
        plan = self.router.rank(
            [candidate(1, "only", quality=0.6, input_price="0", output_price="0")],
            RoutingContext(task_type="code"),
        )
        self.assertEqual(plan.selected.model_key, "only")

    def test_all_filtered_candidates_return_no_selection(self) -> None:
        plan = self.router.rank(
            [candidate(1, "slow", quality=0.9, input_price="0", output_price="0", latency=5000)],
            RoutingContext(max_latency_ms=100),
        )
        self.assertIsNone(plan.selected)
        self.assertIn("avg_latency_ms", plan.candidates[0].rejection_reasons[0])

    def test_quality_and_reliability_thresholds_are_hard_constraints(self) -> None:
        plan = self.router.rank(
            [candidate(1, "weak", quality=0.4, input_price="0", output_price="0", success=0.7)],
            RoutingContext(min_quality=0.8, min_success_rate=0.9),
        )
        reasons = " ".join(plan.candidates[0].rejection_reasons)
        self.assertIn("min_quality", reasons)
        self.assertIn("min_success_rate", reasons)

    def test_budget_uses_tighter_of_user_balance_and_request_limit(self) -> None:
        context = RoutingContext(
            max_request_cost=Decimal("0.02"), budget_remaining=Decimal("0.005"),
        )
        self.assertEqual(context.effective_cost_limit, Decimal("0.005"))

    def test_zero_price_candidate_has_finite_cost_score(self) -> None:
        plan = self.router.rank(
            [candidate(1, "free", quality=0.5, input_price="0", output_price="0")],
            RoutingContext(),
        )
        self.assertEqual(plan.selected.scores["cost"], 0.5)
        self.assertGreaterEqual(plan.selected.weighted_score, 0)

    def test_tie_break_uses_priority_then_model_key(self) -> None:
        plan = self.router.rank(
            [
                candidate(1, "z-model", quality=0.8, input_price="0", output_price="0", priority=10),
                candidate(2, "a-model", quality=0.8, input_price="0", output_price="0", priority=20),
            ],
            RoutingContext(task_type="code"),
        )
        self.assertEqual(plan.selected.model_key, "a-model")

    def test_input_order_does_not_change_selection(self) -> None:
        items = [
            candidate(1, "a", quality=0.7, input_price="0.01", output_price="0.01"),
            candidate(2, "b", quality=0.8, input_price="0.02", output_price="0.02"),
        ]
        context = RoutingContext(task_type="code", estimated_input_tokens=100, expected_output_tokens=100)
        self.assertEqual(
            self.router.rank(items, context).selected.model_key,
            self.router.rank(reversed(items), context).selected.model_key,
        )

    def test_unrelated_expensive_candidate_does_not_change_existing_scores(self) -> None:
        base = [
            candidate(1, "a", quality=0.7, input_price="0.01", output_price="0.01", latency=400),
            candidate(2, "b", quality=0.8, input_price="0.02", output_price="0.02", latency=600),
        ]
        context = RoutingContext(task_type="code", estimated_input_tokens=100, expected_output_tokens=100)
        first = self.router.rank(base, context)
        expanded = self.router.rank(
            base + [candidate(3, "outlier", quality=0.1, input_price="100", output_price="100", latency=50000)],
            context,
        )
        first_scores = {item.model_key: item.scores for item in first.candidates}
        expanded_scores = {item.model_key: item.scores for item in expanded.candidates}
        self.assertEqual(first_scores["a"], expanded_scores["a"])
        self.assertEqual(first_scores["b"], expanded_scores["b"])

    def test_small_profile_sample_has_lower_confidence(self) -> None:
        context = RoutingContext(task_type="code", minimum_profile_samples=20)
        low = self.router.rank(
            [candidate(1, "low", quality=1, input_price="0", output_price="0", sample_count=1)], context
        ).selected
        high = self.router.rank(
            [candidate(1, "high", quality=1, input_price="0", output_price="0", sample_count=20)], context
        ).selected
        self.assertLess(low.profile_confidence, high.profile_confidence)
        self.assertLess(low.scores["quality"], high.scores["quality"])

    def test_stale_profile_has_lower_confidence(self) -> None:
        context = RoutingContext(task_type="code", profile_half_life_days=30)
        fresh = self.router.rank(
            [candidate(1, "fresh", quality=1, input_price="0", output_price="0", profile_age_days=0)], context
        ).selected
        stale = self.router.rank(
            [candidate(1, "stale", quality=1, input_price="0", output_price="0", profile_age_days=60)], context
        ).selected
        self.assertEqual(fresh.profile_confidence, 1)
        self.assertAlmostEqual(stale.profile_confidence, 0.25)

    def test_low_confidence_blends_all_profile_dimensions_with_explicit_priors(self) -> None:
        item = replace(
            candidate(1, "prior-backed", quality=1, input_price="0", output_price="0", sample_count=0),
            profile_latency_score=1,
            profile_cost_score=1,
            profile_reliability_score=1,
            quality_prior_score=.2,
            latency_prior_score=.3,
            cost_prior_score=.4,
            reliability_prior_score=.6,
        )
        selected = self.router.rank([item], RoutingContext(quality_uncertainty_penalty=0)).selected
        self.assertEqual(
            selected.scores,
            {"quality": .2, "latency": .3, "cost": .4, "reliability": .6,
             "task": .5, "context": 1.0, "budget": .5},
        )

    def test_explicit_request_cost_is_used_for_budget_constraint(self) -> None:
        item = replace(
            candidate(1, "estimated", quality=.8, input_price="0", output_price="0"),
            estimated_request_cost=Decimal("0.02"),
        )
        plan = self.router.rank([item], RoutingContext(max_request_cost=Decimal("0.01")))
        self.assertIsNone(plan.selected)
        self.assertIn("estimated_cost", plan.candidates[0].rejection_reasons[0])

    def test_weight_normalization_rejects_negative_nan_and_unknown_values(self) -> None:
        weights = normalize_weights({"quality": float("nan"), "cost": -1, "unknown": 999})
        self.assertAlmostEqual(sum(weights.values()), 1)
        self.assertEqual(weights["quality"], 0)
        self.assertEqual(weights["cost"], 0)

    def test_all_zero_weights_fall_back_to_defaults(self) -> None:
        self.assertEqual(normalize_weights({name: 0 for name in DEFAULT_WEIGHTS}), DEFAULT_WEIGHTS)

    def test_capability_parser_accepts_json_csv_and_mapping(self) -> None:
        self.assertEqual(parse_capabilities('["Vision", "code"]'), {"vision", "code"})
        self.assertEqual(parse_capabilities("vision, code"), {"vision", "code"})
        self.assertEqual(parse_capabilities('{"vision": true, "audio": false}'), {"vision"})

    def test_token_estimate_is_deterministic_and_handles_empty_input(self) -> None:
        self.assertEqual(estimate_message_tokens([]), 0)
        self.assertEqual(estimate_message_tokens(["abcdef"]), 2)
        self.assertEqual(estimate_message_tokens(["abc", "def"]), 2)


if __name__ == "__main__":
    unittest.main()
