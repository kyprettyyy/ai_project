# Results and evidence status

## Current evidence level

The committed report is a **synthetic smoke test**, generated from 12 observations covering four requests and three placeholder models. It verifies that the static and feedback strategies are behaviorally distinct, selection is isolated from held-out outcomes, the production router is reused, and reporting works. It cannot support a claim about real LLM performance.

Static weighted routing and EvalRoute feedback no longer tie on the fixture. Static weighted selects from immutable model priors and records mean quality `0.8275`, mean latency `462.50 ms`, and mean cost `0.005500`. Feedback routing selects from training-derived profiles through the production seven-dimensional router and records `0.7925`, `382.50 ms`, and `0.004000`. These numbers show different code paths and trade-offs; they do not show that either policy is superior on real data.

## Integrity controls

- all policies select without reading `observed_*`;
- final metrics and Pareto analysis read only `observed_*`;
- the former ambiguous outcome field names are rejected;
- empirical rows require complete quality, latency, cost, reliability, sample-count, and age profiles;
- the immutable prior input and observation input receive separate SHA-256 hashes;
- a regression test replaces every held-out outcome with adversarial values and confirms unchanged selections.

## Experiment matrix

The offline suite contains eight policy baselines, five objective-weight presets, seven production-dimension ablations, model unavailability and profile drift/failure scenarios, repeated random trials, and model-level observed quality/latency/cost Pareto analysis.

Every policy report includes task quality, mean and P95 latency, mean and total cost, success rate, observed constraint-violation rate, selected-model distribution, and an auxiliary utility score. Random-policy intervals describe routing randomness only and are not a substitute for request-level bootstrap analysis.

## Empirical acceptance gate

Results may be described as an empirical benchmark only after recording:

1. dataset name, version, task taxonomy, license, sampling method, and immutable hash;
2. exact model identifiers, provider versions, decoding parameters, price snapshot, and collection time;
3. request-disjoint profile-training, validation, and held-out test splits;
4. the independent static-prior source and the rule used to freeze it before test evaluation;
5. scoring rubric, judge prompt/version, blinded presentation order, and human-audit protocol;
6. failures, exclusions, retries, raw observations, seeds, and paired confidence intervals.

Until then, describe the experiment framework and integrity checks, not a measured performance gain.
