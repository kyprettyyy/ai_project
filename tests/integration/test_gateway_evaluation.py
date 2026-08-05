from __future__ import annotations

import importlib.util
import sys
import unittest
from decimal import Decimal
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


router_module = load_module(
    "evalroute_explainable_router",
    ROOT / "services" / "gateway" / "app" / "routing" / "explainable_router.py",
)
scoring_module = load_module(
    "evalroute_profile_scoring",
    ROOT / "services" / "evaluation" / "app" / "scoring" / "profile_scoring.py",
)


class GatewayEvaluationFeedbackTest(unittest.TestCase):
    def test_new_evaluation_profile_changes_routing_choice(self) -> None:
        CandidateSignals = router_module.CandidateSignals
        RoutingContext = router_module.RoutingContext
        engine = router_module.ExplainableRouter()
        context = RoutingContext(task_type="code", estimated_input_tokens=500, expected_output_tokens=500)

        def signals(quality_a: float, quality_b: float):
            return [
                CandidateSignals(
                    model_id=1, model_key="cheap-model", context_length=32000,
                    input_price=Decimal("0.001"), output_price=Decimal("0.001"),
                    avg_latency_ms=300, live_success_rate=0.99, quality_score=quality_a,
                    profile_cost_score=1, profile_reliability_score=0.99,
                    profile_latency_score=0.8, sample_count=40, profile_version=1,
                    profile_task_type="code",
                ),
                CandidateSignals(
                    model_id=2, model_key="quality-model", context_length=32000,
                    input_price=Decimal("0.02"), output_price=Decimal("0.02"),
                    avg_latency_ms=400, live_success_rate=0.99, quality_score=quality_b,
                    profile_cost_score=0.2, profile_reliability_score=0.99,
                    profile_latency_score=0.7, sample_count=40, profile_version=2,
                    profile_task_type="code",
                ),
            ]

        weights = {"quality": 0.8, "cost": 0.1, "latency": 0.025, "reliability": 0.025,
                   "task": 0.025, "context": 0.0125, "budget": 0.0125}
        before = engine.rank(signals(0.6, 0.6), context, weights)
        self.assertEqual(before.selected.model_key, "cheap-model")

        observations = []
        for _ in range(20):
            observations.extend([
                {"model_name": "cheap-model", "user_rating": 2,
                 "ai_score": '{"averageRating":3,"correctness":0.2}', "latency": 300,
                 "cost": 0.001, "output_text": "weak", "task_config": '{"taskType":"code"}'},
                {"model_name": "quality-model", "user_rating": 5,
                 "ai_score": '{"averageRating":10,"correctness":1}', "latency": 400,
                 "cost": 0.02, "output_text": "correct", "task_config": '{"taskType":"code"}'},
            ])
        profiles = scoring_module.build_profiles(observations, "evaluation-run-2")
        quality = {item["model"]: item["quality_score"] for item in profiles}
        after = engine.rank(signals(quality["cheap-model"], quality["quality-model"]), context, weights)
        self.assertEqual(after.selected.model_key, "quality-model")
        self.assertGreater(after.selected.scores["quality"], before.selected.scores["quality"])


if __name__ == "__main__":
    unittest.main()
