# Current project status — 2026-09-24

## Current implementation

- Escape-room operations assistant: FastAPI API, React/Vite customer and game-master screens, FastMCP tools, LocalRuntime and optional PostgreSQL repository.
- Agent flow: session/context → LLM INITIAL decision → selected read-only MCP lookup when needed → LLM FOLLOWUP → code-validated action → user/staff response.
- LLM judges intent, context, support need, lookup choice, and follow-up action. Code/MCP enforce session/team scope, approved hint contents, AnswerVault consent, state changes and idempotency.
- OpenRouter runner requires an exact model ID, ZDR eligibility and `data_collection=deny`; current selection policy compares four candidates under a combined $5 ceiling.
- Evaluation includes the fixed core-30 dataset, evaluator-only quality contract, hardcoding audit, eight-axis scorecard, safe per-case CSV, and Langfuse trace/native score export.

## Verification and external dependencies

- Latest local backend suite: 238 passed. Python compileall passed. Offline preflight passed structurally (30 rows, 10 normal/12 boundary/8 failure); official paid-run readiness remains false until team sign-off.
- Baseline isolated smoke completed 30/30 with no provider calls. Its 34/52 automated checks are plumbing metrics, not LLM or domain quality scores. Safe CSV output was produced and tested.
- The quality-contract sign-off is pending in `evals/quality_contract_approval.json`.
- OpenRouter/Langfuse credentials are not included in this repository. No new paid model run or actual Langfuse dashboard write is claimed until the team configures keys and confirms the connection.
- Current official evaluation settings are `evals/TEST_POLICY.md` and `evals/model_selection_policy.json`. Do not use historical hashes, spend records or test counts as current evidence.

## Next team actions

1. Review and approve the current dataset and quality contract; record reviewer/evidence in the approval file.
2. Set OpenRouter and Langfuse credentials locally, set a dedicated OpenRouter key cap at or below $5, and run the four-model ZDR preflight.
3. Run the official selection, review all 30 cases per model with `evals/MODEL_REVIEW_RUBRIC.md`, then publish numeric scores to Langfuse and retain the safe CSV for comparison.
4. Complete Docker/PostgreSQL, deployment and live user-flow checks; fill the required before/after evidence in `EVAL_REPORT.md`.
