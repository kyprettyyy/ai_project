from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "evaluation"))

from app.scoring.profile_scoring import build_profiles


class BatchProfileAggregationTest(unittest.TestCase):
    def test_batch_results_are_grouped_by_model_and_task(self) -> None:
        rows = [
            {
                "model_name": "model-a",
                "user_rating": 5,
                "ai_score": '{"averageRating": 9, "correctness": 1}',
                "latency": 100,
                "cost": 0.01,
                "output_text": "ok",
                "task_config": '{"taskType":"code"}',
            },
            {
                "model_name": "model-a",
                "user_rating": 1,
                "ai_score": '{"averageRating": 2, "correctness": 0}',
                "latency": 300,
                "cost": 0.03,
                "output_text": "",
                "error_message": "timeout",
                "task_config": '{"taskType":"code"}',
            },
            {
                "model_name": "model-b",
                "user_rating": 4,
                "ai_score": '{"averageRating": 8, "correctness": 0.8}',
                "latency": 50,
                "cost": 0.005,
                "output_text": "ok",
                "task_config": '{"taskType":"summary"}',
            },
        ]
        profiles = build_profiles(rows, "run-1")
        self.assertEqual(len(profiles), 2)
        code = next(item for item in profiles if item["task_type"] == "code")
        self.assertEqual(code["sample_count"], 2)
        self.assertEqual(code["reliability_score"], 0.5)
        self.assertEqual(code["evaluation_run_id"], "run-1")


if __name__ == "__main__":
    unittest.main()
