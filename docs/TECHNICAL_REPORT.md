# EvalRoute: An Evaluation-Driven Adaptive LLM Gateway

## Abstract

EvalRoute connects an OpenAI-compatible model gateway with a reproducible evaluation service. Unlike static gateways that route only by price or latency, EvalRoute converts benchmark outcomes into task-aware model capability profiles and uses those profiles during online multi-objective routing.

## System design

The system contains two independently deployable Python services. The gateway manages providers, model metadata, authentication, fallback, billing and traceable routing decisions. The evaluation service manages datasets, batch executions, user ratings, automated judging and reports. Evaluation traffic is forced through the gateway with an explicit model, so provider access and observability remain centralized without contaminating benchmark model selection.

## Feedback loop

Evaluation results are aggregated by model and task. Quality, latency, cost and reliability are normalized to `[0,1]` and published through an authenticated internal API. The gateway versions these profiles and computes a weighted score for each eligible candidate. Requests can select a fixed model or supply custom objective weights. Candidate snapshots and fallback order are persisted for auditability.

## Experiments

The repository provides five reproducible simulations: static versus adaptive routing, objective-weight sensitivity, cost-constrained routing, injected provider failures, and capability-profile drift. Included fixture observations are synthetic and validate the harness only. Claims about production gains require a real dataset version, pinned models, repeated trials and confidence intervals.

## Limitations

Profile quality depends on benchmark coverage and judge reliability. Simple min-max normalization is sensitive to outliers. Current routing is contextual but not a learned bandit, and profile publication is triggered explicitly. Future work includes robust normalization, judge calibration, semantic caching, budget-aware constraints, contextual bandits and Kubernetes deployment.
