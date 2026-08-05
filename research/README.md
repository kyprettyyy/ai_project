# EvalRoute research path

This directory is the narrow review path for the research contribution. It intentionally points to the canonical implementation files instead of copying them, so the offline experiment and integrated gateway cannot drift into separate algorithms.

```text
research/
├── router/       Production routing core and adapter
├── evaluation/   Capability-profile scoring
├── experiments/  Leakage-safe policy evaluation and fixtures
├── tests/        Focused verification commands and coverage map
└── docs/         Method, architecture, results, and report
```

Start with [router](router/README.md), [experiments](experiments/README.md), and [tests](tests/README.md). Application UI, payment, administration, deployment, and other legacy platform features are outside this path.
