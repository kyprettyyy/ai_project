# Architecture

## Service boundaries

Gateway owns provider credentials, model inventory, routing, fallback, billing and request audit. Evaluation owns benchmark definitions, test tasks, model outputs, ratings, judge scores, reports and capability-profile snapshots. Neither service reads the other service's database.

## Adaptive score

For model `m`, task `t` and normalized weights `w`, the router computes:

`S(m,t) = wq·Q(m,t) + wl·L(m,t) + wc·C(m,t) + wr·R(m,t)`

All four profile dimensions are in `[0,1]`, where larger is better. Default weights are `0.45 / 0.20 / 0.20 / 0.15`. If a task-specific profile is missing, the router uses the general profile; if no evaluated profile exists, it falls back to gateway health and price statistics.

Each adaptive decision stores the profile version, candidate metrics, final scores, chosen model and fallback order. Explicit `model` requests bypass adaptive selection and use fixed routing.

## Failure behavior

The router excludes inactive and unhealthy models, orders remaining candidates deterministically, and retries a bounded fallback list. Evaluation calls are traceable with `X-Eval-Run-Id`, while ordinary traffic receives a gateway trace ID.
