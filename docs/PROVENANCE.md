# Project Origins and Contributions

## Project origins

EvalRoute was developed by integrating and extending two publicly available educational projects:

- [AI 大模型评测平台](https://github.com/yuyuanweb/ai-test), which provided the original model-evaluation platform structure and parts of the evaluation frontend;
- [Yu-AI-Router](https://github.com/yuyuanweb/yu-ai-router), which provided the original AI gateway platform structure and parts of the gateway frontend.

These upstream projects were published as practical learning projects by 编程导航学习圈. Their original authors retain credit for the corresponding project structures and reused components.

## Adaptation and integration

The original projects used independent Java, Go, and Python implementations. This repository integrates selected concepts and components into a unified Python-based prototype, including:

- adaptation of frontend API calls to the current FastAPI services;
- integration of the gateway and evaluation workflows;
- shared local deployment and database configuration;
- unified request, evaluation, profile, and routing data flows.

The legacy user-management, payment, plugin, image-generation, administration, and frontend features are supporting integration context rather than the primary research contribution.

## Original research contribution

The main contribution of this repository is the evaluation-guided LLM-routing research path, including:

- constraint-aware and explainable multi-objective model selection;
- stable reference-based latency and cost scoring;
- task-specific capability profiles;
- sample-confidence and profile-freshness adjustment;
- routing decision and fallback explanations;
- offline baseline, sensitivity, ablation, failure, and drift experiments;
- experiment validation, focused tests, methodology, and result reporting.

The main implementation is located in:

- `services/gateway/app/routing/explainable_router.py`;
- `services/gateway/app/services/adaptive_routing_service.py`;
- `services/evaluation/app/scoring/profile_scoring.py`;
- `experiments/`;
- `tests/`;
- `docs/`.

## Attribution

Thanks to 编程导航学习圈 and the maintainers of the two upstream projects for publishing the original educational materials and source code.
