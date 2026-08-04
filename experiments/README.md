# Reproducible routing experiments

Run `python experiments/run_experiments.py`. The script writes JSON and Markdown summaries to `experiments/results/`.

The five experiments are:

1. static model versus adaptive policy;
2. quality-first versus balanced versus latency-first weights;
3. unconstrained versus cost-constrained selection;
4. fallback behavior under deterministic failure injection;
5. routing changes after capability-profile drift.

`fixtures/demo_observations.jsonl` is synthetic. Its outputs prove that the experiment and reporting pipeline works; they are not benchmark claims. Replace the fixture with exported real observations before citing numbers.
