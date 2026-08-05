# Routing experiment results

> Evidence level: **synthetic_demo**. Synthetic fixture output; do not cite as an empirical model benchmark.

## Run metadata

- Observations: 12
- Requests: 4
- Models: model-a, model-b, model-c
- Repeats: 30
- Router dimensions: quality, latency, cost, reliability, task, context, budget
- Selection inputs: profile_* and immutable static priors only
- Metric inputs: observed_* only
- Static-prior SHA-256: b91cb166ec65c4bb04d020c9338357c0c887eefa8e623c5a1d9508b881c31ba8

## Baseline comparison

| Policy | Quality | Mean latency (ms) | P95 latency (ms) | Mean cost | Success | Violations | Utility |
|---|---:|---:|---:|---:|---:|---:|---:|
| fixed_strongest | 0.8450 | 812.50 | 910.00 | 0.012000 | 1.0000 | 0.7500 | 0.6031 |
| fixed_cheapest | 0.7100 | 265.00 | 300.00 | 0.002000 | 0.7500 | 0.0000 | 0.6502 |
| random | 0.8325 | 530.00 | 650.00 | 0.006750 | 1.0000 | 0.0000 | 0.6855 |
| round_robin | 0.8500 | 615.00 | 870.00 | 0.008250 | 1.0000 | 0.5000 | 0.6753 |
| cost_first | 0.7100 | 265.00 | 300.00 | 0.002000 | 0.7500 | 0.0000 | 0.6502 |
| latency_first | 0.7100 | 265.00 | 300.00 | 0.002000 | 0.7500 | 0.0000 | 0.6502 |
| static_weighted | 0.8275 | 462.50 | 560.00 | 0.005500 | 1.0000 | 0.0000 | 0.7031 |
| evalroute_feedback | 0.7925 | 382.50 | 560.00 | 0.004000 | 1.0000 | 0.0000 | 0.6951 |

## Weight Sensitivity

```json
{
  "quality_first": {
    "requests": 4,
    "mean_quality": 0.8125,
    "mean_latency_ms": 420.0,
    "p95_latency_ms": 560.0,
    "mean_cost": 0.00475,
    "total_cost": 0.019,
    "success_rate": 1.0,
    "constraint_violation_rate": 0.0,
    "utility": 0.702,
    "model_distribution": {
      "model-b": 0.75,
      "model-c": 0.25
    }
  },
  "balanced": {
    "requests": 4,
    "mean_quality": 0.7925,
    "mean_latency_ms": 382.5,
    "p95_latency_ms": 560.0,
    "mean_cost": 0.004,
    "total_cost": 0.016,
    "success_rate": 1.0,
    "constraint_violation_rate": 0.0,
    "utility": 0.6951,
    "model_distribution": {
      "model-b": 0.5,
      "model-c": 0.5
    }
  },
  "cost_first": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  },
  "latency_first": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  },
  "reliability_first": {
    "requests": 4,
    "mean_quality": 0.7925,
    "mean_latency_ms": 382.5,
    "p95_latency_ms": 560.0,
    "mean_cost": 0.004,
    "total_cost": 0.016,
    "success_rate": 1.0,
    "constraint_violation_rate": 0.0,
    "utility": 0.6951,
    "model_distribution": {
      "model-b": 0.5,
      "model-c": 0.5
    }
  }
}
```

## Ablation

```json
{
  "without_quality": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  },
  "without_latency": {
    "requests": 4,
    "mean_quality": 0.7925,
    "mean_latency_ms": 382.5,
    "p95_latency_ms": 560.0,
    "mean_cost": 0.004,
    "total_cost": 0.016,
    "success_rate": 1.0,
    "constraint_violation_rate": 0.0,
    "utility": 0.6951,
    "model_distribution": {
      "model-b": 0.5,
      "model-c": 0.5
    }
  },
  "without_cost": {
    "requests": 4,
    "mean_quality": 0.7925,
    "mean_latency_ms": 382.5,
    "p95_latency_ms": 560.0,
    "mean_cost": 0.004,
    "total_cost": 0.016,
    "success_rate": 1.0,
    "constraint_violation_rate": 0.0,
    "utility": 0.6951,
    "model_distribution": {
      "model-b": 0.5,
      "model-c": 0.5
    }
  },
  "without_reliability": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  },
  "without_task": {
    "requests": 4,
    "mean_quality": 0.7925,
    "mean_latency_ms": 382.5,
    "p95_latency_ms": 560.0,
    "mean_cost": 0.004,
    "total_cost": 0.016,
    "success_rate": 1.0,
    "constraint_violation_rate": 0.0,
    "utility": 0.6951,
    "model_distribution": {
      "model-b": 0.5,
      "model-c": 0.5
    }
  },
  "without_context": {
    "requests": 4,
    "mean_quality": 0.7925,
    "mean_latency_ms": 382.5,
    "p95_latency_ms": 560.0,
    "mean_cost": 0.004,
    "total_cost": 0.016,
    "success_rate": 1.0,
    "constraint_violation_rate": 0.0,
    "utility": 0.6951,
    "model_distribution": {
      "model-b": 0.5,
      "model-c": 0.5
    }
  },
  "without_budget": {
    "requests": 4,
    "mean_quality": 0.7925,
    "mean_latency_ms": 382.5,
    "p95_latency_ms": 560.0,
    "mean_cost": 0.004,
    "total_cost": 0.016,
    "success_rate": 1.0,
    "constraint_violation_rate": 0.0,
    "utility": 0.6951,
    "model_distribution": {
      "model-b": 0.5,
      "model-c": 0.5
    }
  }
}
```

## Failure And Drift

```json
{
  "normal": {
    "requests": 4,
    "mean_quality": 0.7925,
    "mean_latency_ms": 382.5,
    "p95_latency_ms": 560.0,
    "mean_cost": 0.004,
    "total_cost": 0.016,
    "success_rate": 1.0,
    "constraint_violation_rate": 0.0,
    "utility": 0.6951,
    "model_distribution": {
      "model-b": 0.5,
      "model-c": 0.5
    }
  },
  "model-b_unavailable": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  },
  "model-b_latency_spike": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  },
  "model-b_price_spike": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  },
  "model-b_quality_drop": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  },
  "model-b_stale_profile": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  },
  "model-b_low_sample": {
    "requests": 4,
    "mean_quality": 0.71,
    "mean_latency_ms": 265.0,
    "p95_latency_ms": 300.0,
    "mean_cost": 0.002,
    "total_cost": 0.008,
    "success_rate": 0.75,
    "constraint_violation_rate": 0.0,
    "utility": 0.6502,
    "model_distribution": {
      "model-c": 1.0
    }
  }
}
```

## Interpretation guardrail

These numbers describe the supplied observation file only. A synthetic fixture verifies the evaluation code; it does not establish that EvalRoute improves real model quality, latency, cost, or reliability.
