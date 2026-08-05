from __future__ import annotations

import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "gateway"))

from app.routing.explainable_router import CandidateSignals, ExplainableRouter, RoutingContext


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
        quality_score=quality,
        profile_latency_score=max(0, 1 - latency / 2000),
        profile_cost_score=0.5,
        profile_reliability_score=success,
        sample_count=100,
        profile_version=3,
        profile_task_type="code",
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


if __name__ == "__main__":
    unittest.main()
