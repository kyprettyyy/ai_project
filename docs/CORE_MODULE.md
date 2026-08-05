# Core module: explainable constraint-aware routing

## Decision stages

The pure-Python engine in `services/gateway/app/routing/explainable_router.py` separates feasibility from preference:

1. estimate the request token and monetary requirements;
2. reject models that violate hard constraints;
3. adjust evaluation profiles for sample confidence and age;
4. compute candidate-independent objective scores;
5. rank deterministically and retain explanations for every candidate.

## Hard constraints

A model is ineligible when it cannot fit the estimated context, exceeds the tighter of the per-request cost cap and remaining budget, lacks a required capability, or violates minimum quality, maximum latency, or minimum reliability. Rejected candidates remain in the audit snapshot with exact reasons.

## Stable signals

Latency and request cost use fixed-reference inverse transforms:

`score(x; r) = 1 / (1 + x / r)`

The default references are 1000 ms and 0.01 currency units per request. A value equal to its reference scores 0.5. Unlike candidate-relative min-max scaling, the score of an existing model does not change when an unrelated outlier is added to the candidate set.

Profile confidence combines sample sufficiency and exponential freshness decay:

`sample_confidence = min(1, sample_count / minimum_samples)`

`freshness = 2 ^ (-age_days / half_life_days)`

`confidence = sample_confidence * freshness`

Quality is shrunk toward a neutral 0.5 prior when confidence is low, with an additional bounded uncertainty penalty. Profile latency, cost, and reliability are blended with live/reference signals using the same confidence.

## Ranking score

Eligible models receive seven visible components:

`S = wq·Q + wl·L + wc·C + wr·R + wt·T + wx·X + wb·B`

`Q/L/C/R` are quality, latency, cost, and reliability; `T` is task match; `X` is context headroom; and `B` is budget headroom. Weights are clamped to finite non-negative values and normalized. Invalid or all-zero input falls back to documented defaults.

Budget feasibility and cost efficiency are intentionally distinct: the former is a request-specific hard cap plus remaining headroom, while the latter expresses general price preference. When no request budget exists, budget headroom is neutral rather than duplicating the cost score.

Ties are resolved by score, configured priority, and model key. This makes the result invariant to input order.

## Audit and feedback

Before provider invocation, the integrated gateway stores request context, weights, candidates, rejection reasons, component scores, selected model, profile version, and fallback order. After invocation, the request log records actual model, cost, latency, success, and fallback status. The audit API joins them by trace ID.

Evaluation combines available human, AI-judge, and correctness components with renormalized heuristic weights. Aggregated profiles use the same stable reference transforms as the router and are published with sample counts, timestamps, evaluation-run IDs, and versions.

The closed-loop integration test demonstrates behavior, not empirical superiority: equal-quality profiles favor the cheaper candidate; a later code-task profile with a large quality difference changes the selection under quality-first weights.

## Example

```json
{
  "messages": [{"role": "user", "content": "Review this implementation"}],
  "taskType": "code",
  "routingWeights": {
    "quality": 0.55,
    "cost": 0.15,
    "latency": 0.10,
    "reliability": 0.10,
    "task": 0.05,
    "context": 0.025,
    "budget": 0.025
  },
  "routingConstraints": {
    "maxRequestCost": 0.08,
    "maxLatencyMs": 3000,
    "minSuccessRate": 0.95,
    "expectedOutputTokens": 1200,
    "requiredCapabilities": ["code"],
    "minimumProfileSamples": 20
  }
}
```
