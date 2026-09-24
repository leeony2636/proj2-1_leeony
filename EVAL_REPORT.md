# Model evaluation report

## Current evidence and limits

The current benchmark is `evals/dataset.jsonl` (30 cases; SHA-256 `a30e5f66ded4ca2d6395e70ce88e20039bae6da68f3ca4cb0062826944720df1`). The four-model policy, ZDR gate and combined $5 model-selection budget are defined in `evals/TEST_POLICY.md` and `evals/model_selection_policy.json`.

Automated repository tests and baseline smoke verify software behavior; they do not establish LLM semantic accuracy. No model should be selected from these results until the team approves the current dataset/quality contract, runs the same pipeline and reviews all 30 cases per model. Historical model reports using another dataset or execution path are not part of this run.

Latest local verification: backend tests **238 passed**; `compileall` **PASS**; offline core-30 preflight **PASS** (network not used). Baseline isolated smoke completed 30/30 with zero provider calls and wrote a safe CSV; its 34/52 structural checks are not an LLM quality score. Team quality-contract approval is pending, so official paid-run readiness is **false**. No live OpenRouter or Langfuse connection is represented here.

| Run metadata | Value |
|---|---|
| Run date / run ID | |
| Git commit | |
| Dataset SHA-256 | `a30e5f66ded4ca2d6395e70ce88e20039bae6da68f3ca4cb0062826944720df1` |
| Quality contract SHA-256 | |
| Provider / exact model ID | |
| Prompt / Skill version | |
| Environment | |
| Langfuse project and trace link | |

## Per-model comparison

| Model | 30/30 completed | Human-reviewed PASS | Contract pass | Hard fail | Cost | p50 / p95 | Decision |
|---|---:|---:|---:|---:|---:|---:|---|
| | | | | | | | |
| | | | | | | | |
| | | | | | | | |
| | | | | | | | |

## Eight evaluation axes

| Model | Instruction | Context | Domain | Tool choice | Observation | Decision consistency | Structured output | Efficiency |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| | | | | | | | | |
| | | | | | | | | |
| | | | | | | | | |
| | | | | | | | | |

Use `PASS / PARTIAL / FAIL`; report the numeric mean separately from the strict 30/30 gate. Observation is N/A only when no tool result exists. Efficiency never offsets a quality failure. See `evals/MODEL_REVIEW_RUBRIC.md`.

## Improvement runs and regressions

Change one prompt, skill or code element at a time. Preserve the same case IDs and approved expected outcomes; record both dataset and quality-contract hashes for each run.

| Change | Before run ID | After run ID | Axis changes | Regressed case IDs | Keep / revert and reason |
|---|---|---|---|---|---|
| | | | | | |
| | | | | | |

## Security, operations and release gates

| Gate | Required evidence | Result |
|---|---|---|
| ZDR and spend cap | Current ZDR preflight, dedicated OpenRouter key limit at or below $5 | |
| Human approval | Current dataset/contract hash, reviewer and approval record | |
| Quality | 30/30 complete, final contract 30/30, hard fail 0, required human ratings PASS | |
| Langfuse | Matching traces and per-case numeric Scores; no raw content | |
| Deployment | Compose health, API/MCP flow, PostgreSQL persistence, service URL | |
| Before/after evidence | Same approved data, per-axis changes, regressions explained | |

Actual customer text, model responses, hint/answer text and reviewer prose stay out of the shareable CSV and Langfuse scores. Retain the safe case CSV and Langfuse traces as the comparison artifacts; keep raw runner JSON only as temporary local review input.

## Known weakness and next action

<!-- State the largest measured failure, its case ID, the observed decision, and the next controlled change. -->
