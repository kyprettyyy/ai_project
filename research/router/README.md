# Router

Canonical implementation:

- [`services/gateway/app/routing/explainable_router.py`](../../services/gateway/app/routing/explainable_router.py) — dependency-free seven-dimensional ranking, hard constraints, uncertainty fusion, deterministic ordering, and explanations;
- [`services/gateway/app/services/adaptive_routing_service.py`](../../services/gateway/app/services/adaptive_routing_service.py) — database-to-domain adapter used by the integrated gateway.

The experiment imports `ExplainableRouter` from the first file directly. There is no experiment-only copy of the feedback algorithm.
