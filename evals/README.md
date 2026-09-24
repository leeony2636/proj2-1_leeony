# Evaluation workflow

Use these as the single evaluation entry points:

- `TEST_POLICY.md` and `model_selection_policy.json`: fixed cases, ZDR and cost gates.
- `dataset.jsonl` and `core30_quality_contract.json`: current input set and evaluator-only automatic checks.
- `quality_contract_approval.json`: team sign-off; starts pending and must be completed after review.
- `MODEL_REVIEW_RUBRIC.md`: human score criteria for the six semantic axes.
- `run_model_selection.py`: gated four-model evaluation, traces and numeric Langfuse scores.
- `run_llm_eval.py`: isolated service-flow run. JSON output under `evals/results/live_runs/` is temporary working material and is Git-ignored.
- `score_reviewed_results.py`: aggregate human-reviewed cases and optionally publish scores.

The runner writes a shareable case metrics CSV under `evals/results/model_selection_csv/`. CSV contains run/model/case identifiers, trace IDs, axis statuses, tokens, cost and latency; it excludes customer utterances, model responses, hints, answers and reviewer prose. Langfuse stores numeric scores on the matching trace. Keep the CSV and Langfuse run as the durable comparison record; do not commit raw working JSON.

This dataset is not established as a fully approved domain ground truth until the team completes the hash-bound sign-off. Offline baseline is a plumbing smoke only, not a model-quality result. See `docs/EVALUATION.md` for the exact run and review steps.
