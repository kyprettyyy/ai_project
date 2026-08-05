from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments"))

from routing_experiments import (
    Constraints,
    References,
    aggregate,
    inverse_reference_score,
    load_observations,
    normalize_weights,
    pareto_front,
    percentile,
    run_suite,
    select_policy,
    summarize_trials,
    validate_observations,
    validate_empirical_profiles,
)


def fixture() -> list[dict]:
    return [
        {"request": "r1", "task": "code", "model": "a", "quality": .9, "latency_ms": 900, "cost": .02, "success": 1},
        {"request": "r1", "task": "code", "model": "b", "quality": .75, "latency_ms": 300, "cost": .004, "success": 1},
        {"request": "r2", "task": "summary", "model": "a", "quality": .85, "latency_ms": 800, "cost": .018, "success": 1},
        {"request": "r2", "task": "summary", "model": "b", "quality": .70, "latency_ms": 250, "cost": .003, "success": 0},
    ]


class RoutingExperimentTest(unittest.TestCase):
    def test_validation_rejects_empty_missing_duplicate_and_out_of_range_rows(self) -> None:
        with self.assertRaises(ValueError):
            validate_observations([])
        with self.assertRaises(ValueError):
            validate_observations([{"request": "r"}])
        with self.assertRaises(ValueError):
            validate_observations(fixture() + [dict(fixture()[0])])
        invalid = fixture()
        invalid[0] = {**invalid[0], "quality": 2}
        with self.assertRaises(ValueError):
            validate_observations(invalid)

    def test_jsonl_loader_validates_rows(self) -> None:
        import json
        rows = load_observations([json.dumps(row) for row in fixture()])
        self.assertEqual(len(rows), 4)

    def test_empirical_run_requires_precomputed_profiles(self) -> None:
        with self.assertRaises(ValueError):
            validate_empirical_profiles(fixture())
        profiled = [
            {**row, "profile_quality": .5, "profile_reliability": .9, "profile_sample_count": 20}
            for row in fixture()
        ]
        validate_empirical_profiles(profiled)

    def test_reference_score_is_candidate_set_independent(self) -> None:
        self.assertEqual(inverse_reference_score(10, 10), .5)
        self.assertEqual(inverse_reference_score(0, 10), 1)

    def test_weight_normalization_handles_invalid_values(self) -> None:
        weights = normalize_weights({"quality": float("inf"), "latency": -1, "cost": 2, "reliability": 0})
        self.assertEqual(weights["cost"], 1)
        self.assertAlmostEqual(sum(weights.values()), 1)

    def test_policies_select_one_candidate_per_request(self) -> None:
        for policy in ("fixed_strongest", "fixed_cheapest", "random", "round_robin", "cost_first", "latency_first", "static_weighted", "evalroute_feedback"):
            with self.subTest(policy=policy):
                self.assertEqual(len(select_policy(fixture(), policy)), 2)

    def test_random_policy_is_reproducible_for_a_seed(self) -> None:
        first = [row["model"] for row in select_policy(fixture(), "random", seed=7)]
        second = [row["model"] for row in select_policy(fixture(), "random", seed=7)]
        self.assertEqual(first, second)

    def test_evalroute_enforces_cost_constraint(self) -> None:
        chosen = select_policy(fixture(), "evalroute_feedback", constraints=Constraints(max_cost=.01, max_latency_ms=1000))
        self.assertEqual({row["model"] for row in chosen}, {"b"})
        self.assertEqual(aggregate(chosen)["constraint_violation_rate"], 0)

    def test_aggregate_reports_p95_distribution_and_violations(self) -> None:
        result = aggregate(select_policy(fixture(), "fixed_strongest"), Constraints(max_cost=.01, max_latency_ms=500))
        self.assertEqual(result["requests"], 2)
        self.assertEqual(result["p95_latency_ms"], 900)
        self.assertEqual(result["constraint_violation_rate"], 1)
        self.assertEqual(result["model_distribution"], {"a": 1.0})

    def test_percentile_handles_empty_and_nearest_rank(self) -> None:
        self.assertEqual(percentile([], .95), 0)
        self.assertEqual(percentile([1, 2, 3, 4], .75), 3)

    def test_trial_summary_contains_standard_deviation_and_confidence_interval(self) -> None:
        base = aggregate(select_policy(fixture(), "fixed_cheapest"))
        changed = {**base, "mean_quality": base["mean_quality"] + .1}
        summary = summarize_trials([base, changed])
        self.assertGreater(summary["mean_quality"]["stddev"], 0)
        self.assertLess(summary["mean_quality"]["ci95_low"], summary["mean_quality"]["ci95_high"])

    def test_pareto_front_excludes_dominated_model(self) -> None:
        rows = fixture() + [
            {"request": "r1", "task": "code", "model": "c", "quality": .1, "latency_ms": 2000, "cost": .2, "success": 1},
            {"request": "r2", "task": "summary", "model": "c", "quality": .1, "latency_ms": 2000, "cost": .2, "success": 1},
        ]
        self.assertNotIn("c", pareto_front(rows))

    def test_suite_contains_baselines_ablation_drift_and_stability(self) -> None:
        result = run_suite(fixture(), repeats=5, references=References(), constraints=Constraints())
        self.assertEqual(len(result["baseline_comparison"]), 8)
        self.assertEqual(len(result["ablation"]), 4)
        self.assertGreaterEqual(len(result["failure_and_drift"]), 7)
        self.assertIn("stddev", result["baseline_comparison"]["random"]["stability"]["utility"])


if __name__ == "__main__":
    unittest.main()
