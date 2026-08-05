# EvalRoute: An Explainable Evaluation-Guided LLM Routing Prototype

## Abstract

Applications can access multiple large language models with different quality, latency, price, reliability, context, and capability characteristics. Selecting one fixed model is simple but cannot adapt to task type or operational constraints. EvalRoute studies an alternative: turn offline evaluation outcomes into task-specific capability profiles and use those profiles to make an explainable online selection. The prototype applies hard feasibility constraints before multi-objective ranking, uses stable reference-based transforms for latency and cost, discounts sparse and stale profiles, and records candidate-level explanations. A dependency-free evaluation harness compares eight routing policies and supports sensitivity, ablation, failure, drift, Pareto, and repeated-trial analysis. The committed observations are synthetic and validate the pipeline only; a real-model benchmark remains future work.

## 1. Problem formulation

For request `r`, candidate models differ in task quality, response latency, request cost, success probability, supported capabilities, and context length. The router must choose one eligible model while respecting request-level limits. Some requirements are feasibility conditions: a model that cannot fit the context or exceeds the available budget should not win because of a high quality score. Other requirements are preferences that can be traded off.

EvalRoute therefore separates hard constraints from soft objectives. This separation makes the decision easier to inspect and prevents a weighted sum from hiding an unacceptable violation. The research question is whether evaluation feedback yields better choices than fixed and static policies when all methods are assessed on the same requests.

## 2. System boundary

The research path contains three components. The evaluation scorer combines available correctness, human, and AI-judge signals and aggregates them into task/model profiles. The pure routing engine converts a request and a set of candidate signals into a ranked plan. The offline harness compares policies while separating pre-selection profiles from post-invocation outcomes. A top-level `research/` map provides a narrow review path through these components.

An optional FastAPI integration stores profiles, accepts OpenAI-compatible chat requests, records decisions, invokes providers, and joins estimated decisions with observed outcomes. MySQL, Redis, SDK, deployment scripts, legacy platform features, and migrated Vue interfaces are supporting integration context rather than the core research contribution.

## 3. Constraint-aware routing

The router estimates input and output token requirements and request cost. It rejects a model if its context is too short, its estimated cost exceeds the tighter of the request cap and remaining budget, it lacks a required capability, or it violates configured quality, latency, or reliability thresholds. All rejection reasons remain in the decision snapshot.

Eligible models receive quality, latency, cost, reliability, task match, context headroom, and budget headroom components. The normalized weights are finite, non-negative, and sum to one. Invalid or zero-only overrides fall back to documented defaults. Candidates are sorted by weighted score, then explicit priority, then model key, making the outcome deterministic and invariant to input order.

## 4. Stable normalization and uncertainty

Earlier code normalized latency and cost against the maximum value in the current candidate set. That design is unstable: adding an unrelated expensive model changes every other model's cost score even when none of their prices changed. EvalRoute now uses `1 / (1 + x/r)` with fixed, documented references. The transformation is monotonic, bounded, and candidate-independent. The reference has an intuitive meaning: an observation equal to the reference scores 0.5.

Evaluation profiles are uncertain when they contain few samples or are old. Sample confidence is capped by a minimum-sample target. Freshness follows exponential half-life decay. Their product controls how much the router trusts the profile versus a neutral or live signal. Low-confidence quality is additionally shrunk toward a neutral prior. This is a heuristic, not a calibrated posterior, so its effect must be measured in sensitivity and failure studies.

Cost efficiency and budget feasibility are deliberately different. Cost efficiency is a general preference based on a fixed cost reference. Budget is a request-specific hard limit and remaining-headroom signal. If no budget exists, the budget component is neutral to avoid double-counting cost.

## 5. Evaluation feedback

The profile builder retains individual human, judge, and correctness components. Available components are combined using disclosed heuristic weights and renormalized when a component is missing. Model/task groups report sample count, quality, stable latency/cost scores, reliability, evaluation-run ID, and timestamp.

Evaluation traffic must pin an explicit model. If it uses adaptive selection, the model being evaluated is itself selected by the policy, confounding model capability with routing behavior. Empirical work must also build profiles from training data, choose settings on validation data, and evaluate on held-out requests. The current smoke fixture does not satisfy this separation and cannot support a performance conclusion.

## 6. Experimental design

The offline harness compares fixed strongest, fixed cheapest, random, round-robin, cost-first, latency-first, static weighted, and feedback routing. Static weighted uses a separately frozen four-signal model-prior configuration. Feedback routing converts training-derived profiles to production `CandidateSignals` and calls the same seven-dimensional `ExplainableRouter` used online. Five weight presets test objective sensitivity, and seven ablations remove one production-router dimension at a time. Failure and drift scenarios cover unavailability, latency and price spikes, quality degradation, stale profiles, and one-sample profiles.

Each observation has two namespaces. `profile_*` contains only information available before selection; `observed_*` contains the held-out quality, latency, cost, and success used after selection. Neither policy selection nor baseline construction reads `observed_*`. Conversely, aggregate metrics and Pareto analysis read only `observed_*`. Immutable prior and observation files are hashed separately in the report.

Random routing is repeated under deterministic seeds, and the harness reports mean, standard deviation, and a normal-approximation 95% interval. An empirical report should add request-level bootstrap intervals and paired comparisons. Pareto analysis identifies model-level trade-offs without collapsing quality, latency, and cost into a single subjective utility.

## 7. Verification

Focused tests cover empty and single candidate sets, all-candidate rejection, cost/context/capability/quality/latency/reliability constraints, invalid and zero weights, deterministic ties, input-order invariance, zero-cost models, candidate-set-independent scoring, sparse and stale profiles, capability parsing, and token estimation. Experiment tests additionally prove policy separation on feasible candidates, complete pre/post schema validation, immutable-prior coverage, selection invariance under adversarial held-out-outcome changes, observed-only aggregation, all seven production dimensions, reproducible random seeds, constraints, P95, Pareto dominance, and suite completeness. Evaluation and integration tests cover score aggregation and a profile update changing a routing decision.

The dependency-free research verifier runs the router, evaluation, experiment, and feedback-loop suites and regenerates the synthetic report. Broader CI also compiles the services, tests the SDK, and builds the frontends, but these checks do not establish production readiness.

## 8. Current result

On the 12-row synthetic fixture, static weighted and feedback routing now make different choices. Static routing uses only immutable priors; feedback routing uses training-derived profiles through the production engine. Feedback is cheaper and faster but lower-quality than static on this fixture. This demonstrates policy separation and metric behavior only, not empirical superiority.

## 9. Limitations and threats to validity

The main limitation is the absence of a sufficiently large, held-out real-model benchmark. AI judges may be biased by verbosity, order, and model family. Provider prices and latency change over time. The reference transforms, immutable baseline priors, and fusion weights are heuristic. Latency measurements depend on geography and load. Synthetic failure injection is not equivalent to a production incident. The integrated services have not completed security, load, recovery, or cross-provider streaming validation.

## 10. Future work

The next milestone is a 200–500 example multilingual benchmark spanning coding, summarization, extraction, classification, reasoning, and general question answering across three to five candidate models. The study should pin model versions and prices, blind and audit judge outputs, separate profile/validation/test data, report paired bootstrap intervals, and publish failure cases. Later work can compare robust fixed references with historical quantiles, calibrate confidence penalties, detect profile drift, and learn routing weights or a contextual policy on training data.

## Conclusion

EvalRoute's contribution is not a claim of production-scale infrastructure or benchmark superiority. It is a reviewable research prototype that makes feasibility, uncertainty, trade-offs, and evidence boundaries explicit. The project is designed so that a reviewer can run the core, inspect each decision, and distinguish implemented mechanics from experimental claims and planned validation.
