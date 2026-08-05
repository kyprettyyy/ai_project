# Reproducible routing experiments

Run the dependency-free synthetic smoke test:

```powershell
python experiments/run_experiments.py
```

The suite compares eight policies, five weight presets, seven production-router ablations, failure/drift scenarios, Pareto-efficient models, model distributions, and repeated-trial uncertainty summaries.

## Two independent weighted policies

`static_weighted` scores only immutable per-model values from `config/static_model_priors.json`: `quality_prior`, `latency_prior`, `cost_prior`, and `reliability_prior`. It cannot access a row's profile or outcome.

`evalroute_feedback` converts each row's training-derived profile into `CandidateSignals` and calls `services/gateway/app/routing/explainable_router.py`. It therefore uses the same quality, latency, cost, reliability, task, context, and budget dimensions and the same default weights as the integrated gateway.

## Leakage-safe row contract

Input is JSONL with one row per request/model pair:

```json
{
  "request": "r1",
  "task": "code",
  "model": "model-a",
  "profile_quality": 0.82,
  "profile_latency_ms": 720,
  "profile_cost": 0.009,
  "profile_reliability": 0.97,
  "profile_sample_count": 50,
  "profile_age_days": 3,
  "observed_quality": 0.86,
  "observed_latency_ms": 810,
  "observed_cost": 0.011,
  "observed_success": 1
}
```

Selection uses only immutable priors, `profile_*`, and optional request-before-call fields. Aggregation and Pareto analysis use only `observed_*`. The loader rejects the former ambiguous `quality`/`latency_ms`/`cost`/`success` schema and partial profiles for every evidence level.

The synthetic fixture verifies behavior only. Real input must follow `docs/METHODOLOGY.md` and `benchmark/DATASET_CARD.md`, especially the request-level split between profile construction and held-out outcomes.
