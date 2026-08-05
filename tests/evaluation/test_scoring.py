from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "evaluation"))

from app.scoring.profile_scoring import combined_quality, normalize_score, parse_ai_scores


class EvaluationScoringTest(unittest.TestCase):
    def test_scores_are_clamped_to_unit_interval(self) -> None:
        self.assertEqual(normalize_score(12, 10), 1.0)
        self.assertEqual(normalize_score(-1, 10), 0.0)

    def test_human_judge_and_correctness_are_combined(self) -> None:
        result = combined_quality({
            "user_rating": 4,
            "ai_score": '{"averageRating": 9, "correctness": 10}',
        })
        self.assertAlmostEqual(result["human"], 0.8)
        self.assertAlmostEqual(result["judge"], 0.9)
        self.assertAlmostEqual(result["correctness"], 1.0)
        self.assertAlmostEqual(result["combined"], 0.89)

    def test_correctness_accepts_percentage_scale(self) -> None:
        _, correctness = parse_ai_scores({"correctnessScore": 75})
        self.assertEqual(correctness, 0.75)


if __name__ == "__main__":
    unittest.main()
