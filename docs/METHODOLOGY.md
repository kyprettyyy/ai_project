# Evaluation methodology

1. Pin dataset name, version, task type and license in the Dataset Card.
2. Pin model IDs, decoding parameters, judge model and prompt version.
3. Route every evaluation request through Gateway with an explicit model ID.
4. Combine deterministic metrics, human ratings and AI Judge scores. Keep their raw components; do not report only one opaque composite number.
5. Report latency distribution, token usage, cost, failures and sample count alongside quality.
6. Publish model profiles only after the minimum sample threshold is reached.
7. Compare routing policies using the same request trace and bootstrap confidence intervals when enough real samples exist.

AI Judge outputs can be biased by verbosity, ordering and model family. Randomize presentation order, use blinded model labels, retain the rubric, and audit a stratified human sample. Demo fixtures in this repository validate software behavior only and must not be presented as empirical model results.
