# Results and evidence status

## Current evidence level

The committed report is a **synthetic smoke test**, generated from 12 observations covering four requests and three placeholder models. It demonstrates that every policy is evaluated on the same request trace and that the reporting code emits the intended metrics. It cannot support a claim about real LLM performance.

The main negative result is that EvalRoute feedback and static weighted routing produce the same selection and metrics on the current fixture. This is expected because the fixture is too small and its profile signals do not provide information beyond the static scores. The project deliberately reports this tie instead of presenting a fabricated improvement.

## Reported metrics

Every policy report includes:

- task quality;
- mean and P95 latency;
- mean and total cost;
- success rate;
- cost/latency constraint-violation rate;
- selected-model distribution;
- an auxiliary utility score.

Random routing is repeated with deterministic seeds. The report includes the mean, standard deviation, and normal-approximation 95% confidence interval across repeats. These intervals describe routing randomness only; they are not a substitute for resampling a sufficiently large empirical dataset.

## Experiment matrix

The offline suite contains:

1. eight policy baselines;
2. five objective-weight presets;
3. four one-signal ablations;
4. unavailability, latency spike, price spike, quality drop, stale-profile, and low-sample scenarios;
5. model-level quality/latency/cost Pareto analysis.

Machine-readable and reviewer-friendly outputs are stored in `experiments/results/demo-results.json` and `experiments/results/demo-results.md`.

## Empirical acceptance gate

Results may be described as an empirical benchmark only after all of the following are recorded:

1. dataset name, version, task taxonomy, license, sampling method, and immutable hash;
2. exact model identifiers, provider versions, decoding parameters, price snapshot, and collection time;
3. the profile-training/validation/test split, with no test outcome used to construct its own routing signal;
4. scoring rubric, judge prompt/version, blinded presentation order, and human-audit protocol;
5. failed calls, exclusions, retries, raw observations, repeated-run seeds, and confidence intervals.

Until then, resume bullets must describe the experiment **framework**, not a measured performance gain.
