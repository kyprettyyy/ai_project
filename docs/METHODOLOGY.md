# Evaluation methodology

## Research question and hypotheses

The primary question is whether evaluation-derived, task-specific feedback improves model routing under multiple operational constraints. The planned hypotheses are:

- H1: feedback routing improves quality at a matched cost budget compared with static policies;
- H2: hard feasibility filtering reduces request-level cost and latency violations;
- H3: confidence/freshness adjustment improves robustness when profiles are sparse or stale;
- H4: each quality, latency, cost, and reliability signal makes a measurable contribution in at least one task regime.

The current synthetic fixture does not test these hypotheses. It tests the software used to test them.

## Data unit and split

One observation represents one request/model pair but has two explicit time boundaries. `profile_quality`, `profile_latency_ms`, `profile_cost`, `profile_reliability`, `profile_sample_count`, and `profile_age_days` are computed from profile-training data and are available before selection. `observed_quality`, `observed_latency_ms`, `observed_cost`, and `observed_success` are held-out outcomes available only after selection. The experiment rejects rows that omit either side of this contract.

An empirical study must split requests before building profiles:

1. profile-training data estimates task/model capability;
2. validation data selects heuristic weights or other hyperparameters;
3. held-out test data evaluates policy selections.

The outcome for a held-out request must never be used to create the profile used to route that same request. Selection code cannot access `observed_*`; metric aggregation cannot substitute `profile_*`. A regression test mutates every held-out outcome and verifies that all eight policy selections remain unchanged. The demo fixture is synthetic but follows the same schema.

## Reproducibility controls

Pin and retain:

- dataset name, source URL, version, license, task label, split, and file hash;
- model/provider IDs, API versions, decoding parameters, system prompts, and collection timestamps;
- provider price snapshot and token accounting method;
- judge model, rubric, prompt hash, retry policy, and randomized presentation order;
- random seeds, failures, exclusions, and raw unaggregated observations.

Evaluation calls should specify an explicit model rather than using adaptive routing. Otherwise the measured model is confounded with the policy being evaluated.

## Baselines

The harness compares fixed strongest, fixed cheapest, random, round-robin, cost-first, latency-first, static weighted, and EvalRoute feedback routing. Fixed and static baselines use a separately hashed immutable prior configuration. Cost-first and latency-first use training-derived estimates. EvalRoute feedback delegates to the production `ExplainableRouter`. All policies receive the same held-out trace, and observed violations are reported rather than used during selection.

The fixed-strongest model and any learned policy parameters must be chosen using training/validation data, never the held-out outcomes.

## Sensitivity and ablation

Five presets vary the objective emphasis: quality-first, balanced, cost-first, latency-first, and reliability-first. Seven ablations remove each production-router dimension—quality, latency, cost, reliability, task, context, and budget—and let the core router renormalize the rest. The empirical report should compare the change in each raw metric, not only the auxiliary utility value.

## Failure and drift

The suite tests a model becoming unavailable, a latency spike, a price spike, a quality drop, a 90-day-old profile, and a one-sample profile. Empirical fault injection should define exactly when the change begins and compare selection distribution before and after the event.

## Metrics and uncertainty

Report task quality, mean and P95 latency, mean and total cost, success rate, constraint-violation rate, and model-selection distribution. Utility is secondary and its coefficients must be disclosed.

Random policies run with deterministic seeds. For sufficiently large empirical samples, use request-level bootstrap confidence intervals and paired comparisons because every policy is evaluated on the same requests. Report sample size, standard deviation, interval method, and number of resamples.

## Quality measurement

Prefer deterministic correctness metrics where a task permits them. Human ratings and AI-as-a-judge scores must retain their raw components. AI judges may favor verbosity, position, style, or related model families; use blinded labels, randomized order, a fixed rubric, and a stratified human audit. Inter-rater agreement should be reported when multiple humans label the same examples.

## Reporting rule

Synthetic outputs may be described as unit/smoke-test evidence only. A resume may claim design and implementation of the framework now; it may claim a measured improvement only after the empirical acceptance gate in `docs/RESULTS.md` is satisfied.
