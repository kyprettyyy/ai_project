# Reproducible routing experiments

Run the dependency-free smoke test:

```powershell
python experiments/run_experiments.py
```

The suite reports eight routing policies, five weight presets, four signal ablations, six failure/drift scenarios, Pareto-efficient models, model distributions, standard deviation, and 95% confidence intervals. Outputs are written as JSON and Markdown under `experiments/results/`.

Input is JSONL with one row per request/model pair:

```json
{"request":"r1","task":"code","model":"model-a","quality":0.84,"latency_ms":820,"cost":0.012,"success":1}
```

Optional synthetic fields include `profile_quality`, `profile_reliability`, `profile_sample_count`, `minimum_profile_samples`, `profile_age_days`, and `profile_half_life_days`. The first three become mandatory when `--evidence-level empirical` is used, ensuring policy scores come from precomputed profiles rather than each held-out request's own outcome.

`fixtures/demo_observations.jsonl` is synthetic. It verifies program behavior and report structure only. Do not cite its numbers as model-performance evidence. Real input must follow `docs/METHODOLOGY.md` and `benchmark/DATASET_CARD.md`, especially the no-leakage split between profile construction and held-out policy evaluation.
