# Provenance and contribution boundaries

## Purpose

This document records what is known about the repository's sources. It is a transparency and engineering-control document, not legal advice and not proof that every unidentified file is original.

## Known upstream relationships

| Local path | Upstream | Evidence | License status on 2026-08-05 | Required action |
|---|---|---|---|---|
| `web/evaluation/**` | [`yuyuanweb/ai-test`](https://github.com/yuyuanweb/ai-test), primarily `frontend/**` | Earlier repository audit found many matching Git blob SHA values, which means byte-for-byte identical content; local inspection also found upstream naming and deployment residue | No license grant was found on the upstream repository page | Do not redistribute; obtain written permission or replace with independently implemented code |
| `web/gateway/**` | [`yuyuanweb/yu-ai-router`](https://github.com/yuyuanweb/yu-ai-router), primarily `frontend/**` | Earlier repository audit found many matching Git blob SHA values; local structure and metadata retain the upstream template layout | README claims MIT, but the referenced license text was unavailable | Obtain and preserve the exact license and copyright notice before redistribution; otherwise replace the code |

The upstream repositories also publish Python implementations. Because the current repository entered history as a single large commit and a full upstream clone/hash comparison could not be completed in the current environment, the provenance of `services/gateway/**` and `services/evaluation/**` is **not established by Git history alone**. Their authorship must be supported by earlier working records, an author attestation, or a future file-level comparison before anyone claims them as independently written.

## Current-repository integration work

The following describes the role of the files in this repository, not a claim of exclusive authorship:

- `infrastructure/**`, `scripts/**` and `platform-web/**` connect the local runtime.
- `services/gateway/**` and `services/evaluation/**` implement the current Python service boundary.
- `sdk/python/**` exposes the current gateway API to Python callers.
- `benchmark/**`, `experiments/**` and `docs/**` describe and exercise the evaluation-driven routing concept.
- Frontend API files and environment configuration have been adapted to the current Python endpoints.

### Traceable post-audit core contribution (2026-08-05)

The explainable constraint-aware routing change was added after this provenance audit and is isolated in reviewable paths:

- `services/gateway/app/routing/explainable_router.py`: dependency-free hard constraints, seven-dimensional ranking, confidence blending and explanations;
- `services/gateway/app/services/adaptive_routing_service.py`: ORM-to-domain adapter and decision persistence;
- `services/gateway/app/api/routing_audit.py`: decision/outcome join and profile-generation effect metrics;
- `services/evaluation/app/scoring/profile_scoring.py`: human, AI Judge and correctness aggregation;
- `tests/gateway/**`, `tests/evaluation/**`, `tests/integration/**`: unit and closed-loop evidence.
- `experiments/routing_experiments.py` and `tests/experiments/**`: baseline, sensitivity, ablation, failure/drift and uncertainty evaluation.
- `README.md`, `docs/RESULTS.md` and this document: contribution, evidence and third-party boundaries for academic review.

Historical payment, recharge, balance, billing, blacklist, full user/admin, BYOK, plugin, image-generation, Prompt Lab, WebSocket/STOMP, Nginx and large frontend features are outside the routing research contribution. They should not appear in academic or resume claims about the method.

These paths provide a concrete contribution boundary. Any resume or report should still describe the actual development process and disclose tool/AI assistance when required by the applicable course, employer or competition rules.

## Public-description rules

Until the license and authorship questions above are resolved:

- describe the work as “an integration prototype based on two public projects”;
- identify personal contributions by specific files, features and commits;
- do not claim that the entire project or either frontend was developed from scratch;
- do not describe synthetic experiment output as production or benchmark evidence;
- do not publish, submit or commercially distribute the repository where upstream permission is required.

## Release gate

A public release is blocked until all of the following are recorded:

1. exact upstream commit IDs used for each migrated component;
2. file-level inventory of unchanged, modified and newly created files;
3. authoritative license text and copyright notice for every migrated component;
4. confirmation that license obligations are satisfied, or removal and independent replacement of the affected code;
5. a repository-wide license selected by the owners of the original contributions.

When those items are complete, update `LICENSE`, `NOTICE`, this document and the README together.
