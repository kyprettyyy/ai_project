from __future__ import annotations

import json
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
    load_static_priors,
    normalize_primary_weights,
    pareto_front,
    percentile,
    run_suite,
    select_policy,
    static_prior_score,
    summarize_trials,
    validate_empirical_profiles,
    validate_observations,
    validate_static_priors,
)


def row(request: str, task: str, model: str, **overrides: float) -> dict:
    result = {
        "request": request,
        "task": task,
        "model": model,
        "profile_quality": 0.7,
        "profile_latency_ms": 500,
        "profile_cost": 0.005,
        "profile_reliability": 0.95,
        "profile_sample_count": 20,
        "profile_age_days": 0,
        "observed_quality": 0.7,
        "observed_latency_ms": 500,
        "observed_cost": 0.005,
        "observed_success": 1,
    }
    result.update(overrides)
    return result


def fixture() -> list[dict]:
    return [
        row("r1", "code", "a", profile_quality=.95, profile_latency_ms=900,
            profile_cost=.009, observed_quality=.9, observed_latency_ms=920, observed_cost=.01),
        row("r1", "code", "b", profile_quality=.60, profile_latency_ms=300,
            profile_cost=.003, observed_quality=.75, observed_latency_ms=310, observed_cost=.004),
        row("r2", "summary", "a", profile_quality=.90, profile_latency_ms=800,
            profile_cost=.009, observed_quality=.85, observed_latency_ms=810, observed_cost=.01),
        row("r2", "summary", "b", profile_quality=.55, profile_latency_ms=250,
            profile_cost=.002, profile_reliability=.6, observed_quality=.70,
            observed_latency_ms=260, observed_cost=.003, observed_success=0),
    ]


def priors():
    return load_static_priors({
        "a": {
            "quality_prior": .4, "latency_prior": .4,
            "cost_prior": .4, "reliability_prior": .8,
        },
        "b": {
            "quality_prior": .8, "latency_prior": .8,
            "cost_prior": .8, "reliability_prior": .9,
        },
        "c": {
            "quality_prior": .2, "latency_prior": .2,
            "cost_prior": .2, "reliability_prior": .2,
        },
    })


class RoutingExperimentTest(unittest.TestCase):
    def test_validation_rejects_legacy_missing_duplicate_and_invalid_rows(self) -> None:
        with self.assertRaises(ValueError):
            validate_observations([])
        legacy = {
            "request": "r", "task": "code", "model": "a",
            "quality": .8, "latency_ms": 100, "cost": .01, "success": 1,
        }
        with self.assertRaises(ValueError):
            validate_observations([legacy])
        with self.assertRaises(ValueError):
            validate_observations(fixture() + [dict(fixture()[0])])
        invalid = fixture()
        invalid[0] = {**invalid[0], "observed_quality": 2}
        with self.assertRaises(ValueError):
            validate_observations(invalid)

    def test_jsonl_loader_validates_rows(self) -> None:
        rows = load_observations([json.dumps(item) for item in fixture()])
        self.assertEqual(len(rows), 4)

    def test_empirical_run_requires_complete_precomputed_profiles_and_observations(self) -> None:
        validate_empirical_profiles(fixture())
        incomplete = fixture()
        del incomplete[0]["profile_latency_ms"]
        with self.assertRaises(ValueError):
            validate_empirical_profiles(incomplete)

    def test_static_prior_configuration_is_strict_and_complete(self) -> None:
        validate_static_priors(fixture(), priors())
        with self.assertRaises(ValueError):
            load_static_priors({"a": {"quality_prior": .5}})
        with self.assertRaises(ValueError):
            validate_static_priors(fixture(), {"a": priors()["a"]})

    def test_reference_score_is_candidate_set_independent(self) -> None:
        self.assertEqual(inverse_reference_score(10, 10), .5)
        self.assertEqual(inverse_reference_score(0, 10), 1)

    def test_primary_weight_normalization_handles_invalid_values(self) -> None:
        weights = normalize_primary_weights(
            {"quality": float("inf"), "latency": -1, "cost": 2, "reliability": 0}
        )
        self.assertEqual(weights["cost"], 1)
        self.assertAlmostEqual(sum(weights.values()), 1)

    def test_static_score_accepts_only_prior_object(self) -> None:
        score = static_prior_score(priors()["a"])
        self.assertGreater(score, 0)

    def test_policies_select_one_candidate_per_request(self) -> None:
        policies = (
            "fixed_strongest", "fixed_cheapest", "random", "round_robin",
            "cost_first", "latency_first", "static_weighted", "evalroute_feedback",
        )
        for policy in policies:
            with self.subTest(policy=policy):
                self.assertEqual(len(select_policy(fixture(), policy, static_priors=priors())), 2)

    def test_random_policy_is_reproducible_for_a_seed(self) -> None:
        first = [item["model"] for item in select_policy(fixture(), "random", static_priors=priors(), seed=7)]
        second = [item["model"] for item in select_policy(fixture(), "random", static_priors=priors(), seed=7)]
        self.assertEqual(first, second)

    def test_static_and_feedback_are_distinct_on_feasible_candidates(self) -> None:
        constraints = Constraints(max_cost=.02, max_latency_ms=2000)
        static = [item["model"] for item in select_policy(
            fixture(), "static_weighted", static_priors=priors(), constraints=constraints,
        )]
        feedback = [item["model"] for item in select_policy(
            fixture(), "evalroute_feedback", static_priors=priors(), constraints=constraints,
        )]
        self.assertEqual(static, ["b", "b"])
        self.assertEqual(feedback, ["a", "a"])

    def test_selection_does_not_change_when_held_out_outcomes_change(self) -> None:
        policies = (
            "fixed_strongest", "fixed_cheapest", "random", "round_robin",
            "cost_first", "latency_first", "static_weighted", "evalroute_feedback",
        )
        poisoned = [
            {
                **item,
                "observed_quality": 1 - item["observed_quality"],
                "observed_latency_ms": 999999,
                "observed_cost": 999,
                "observed_success": 1 - item["observed_success"],
            }
            for item in fixture()
        ]
        for policy in policies:
            with self.subTest(policy=policy):
                original = [item["model"] for item in select_policy(
                    fixture(), policy, static_priors=priors(), seed=7,
                )]
                changed = [item["model"] for item in select_policy(
                    poisoned, policy, static_priors=priors(), seed=7,
                )]
                self.assertEqual(original, changed)

    def test_aggregate_uses_observed_values_only(self) -> None:
        chosen = select_policy(fixture(), "static_weighted", static_priors=priors())
        result = aggregate(chosen)
        self.assertEqual(result["mean_quality"], .725)
        self.assertEqual(result["mean_latency_ms"], 285)

    def test_evalroute_enforces_profile_cost_constraint(self) -> None:
        chosen = select_policy(
            fixture(), "evalroute_feedback", static_priors=priors(),
            constraints=Constraints(max_cost=.004, max_latency_ms=1000),
        )
        self.assertEqual({item["model"] for item in chosen}, {"b"})

    def test_aggregate_reports_p95_distribution_and_observed_violations(self) -> None:
        result = aggregate(
            select_policy(fixture(), "fixed_strongest", static_priors=priors()),
            Constraints(max_cost=.005, max_latency_ms=500),
        )
        self.assertEqual(result["requests"], 2)
        self.assertEqual(result["p95_latency_ms"], 310)
        self.assertEqual(result["constraint_violation_rate"], 0)
        self.assertEqual(result["model_distribution"], {"b": 1.0})

    def test_percentile_handles_empty_and_nearest_rank(self) -> None:
        self.assertEqual(percentile([], .95), 0)
        self.assertEqual(percentile([1, 2, 3, 4], .75), 3)

    def test_trial_summary_contains_standard_deviation_and_confidence_interval(self) -> None:
        base = aggregate(select_policy(fixture(), "fixed_cheapest", static_priors=priors()))
        changed = {**base, "mean_quality": base["mean_quality"] + .1}
        summary = summarize_trials([base, changed])
        self.assertGreater(summary["mean_quality"]["stddev"], 0)
        self.assertLess(summary["mean_quality"]["ci95_low"], summary["mean_quality"]["ci95_high"])

    def test_pareto_front_excludes_dominated_model_using_observed_metrics(self) -> None:
        rows = fixture() + [
            row("r1", "code", "c", observed_quality=.1, observed_latency_ms=2000, observed_cost=.2),
            row("r2", "summary", "c", observed_quality=.1, observed_latency_ms=2000, observed_cost=.2),
        ]
        self.assertNotIn("c", pareto_front(rows))

    def test_suite_uses_production_dimensions_for_ablation(self) -> None:
        result = run_suite(
            fixture(), static_priors=priors(), repeats=5,
            references=References(), constraints=Constraints(),
        )
        self.assertEqual(len(result["baseline_comparison"]), 8)
        self.assertEqual(len(result["ablation"]), 7)
        self.assertEqual(result["metadata"]["selection_fields"], "profile_* and immutable static priors only")
        self.assertGreaterEqual(len(result["failure_and_drift"]), 7)
        self.assertIn("stddev", result["baseline_comparison"]["random"]["stability"]["utility"])


if __name__ == "__main__":
    unittest.main()
