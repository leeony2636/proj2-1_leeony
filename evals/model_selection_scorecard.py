"""Eight project-specific evaluation axes without guessing semantic correctness."""

from __future__ import annotations

from typing import Any


HUMAN_AXES = (
    "instruction_adherence",
    "context_understanding",
    "domain_judgment",
    "tool_judgment",
    "observation_interpretation",
    "decision_consistency",
)
SCORECARD_AXES = HUMAN_AXES + ("structured_output_stability", "efficiency")
RATINGS = {"PASS": 1.0, "PARTIAL": 0.5, "FAIL": 0.0}


def final_contract_status(audit: list[dict[str, Any]], provider: str, execution_status: str) -> str:
    if provider == "baseline":
        return "NOT_APPLICABLE_BASELINE"
    reports = [item for item in audit if item.get("stage") == "LLM_CONTRACT"]
    if execution_status != "COMPLETED" or not reports:
        return "FAIL"
    by_stage: dict[str, dict[str, Any]] = {}
    for report in reports:
        by_stage[str(report.get("llm_stage") or "UNKNOWN")] = report
    return "PASS" if by_stage and all(item.get("normalized_contract_valid") is True for item in by_stage.values()) else "FAIL"


def build_scorecard(
    *,
    provider: str,
    execution_status: str,
    audit: list[dict[str, Any]],
    case_evaluation: dict[str, Any],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    checks = case_evaluation.get("automatic_checks") or {}
    quality_gate = case_evaluation.get("quality_contract_gate") or {}
    lookup = next((item for item in reversed(audit) if item.get("stage") == "LOOKUP_RESULTS"), {})
    initial = next((item for item in reversed(audit) if item.get("stage") == "INITIAL_DECISION"), {})
    followup = next((item for item in reversed(audit) if item.get("stage") == "FOLLOWUP_DECISION"), {})
    observation_applicable = bool(lookup.get("executed_tools") or followup)
    structured_status = final_contract_status(audit, provider, execution_status)

    def pending(**evidence: Any) -> dict[str, Any]:
        return {"status": "PENDING_REVIEW", "automatic_evidence": evidence}

    scorecard = {
        "instruction_adherence": pending(
            contract_final_status=structured_status,
            auto_spoiler_guard=(quality_gate.get("automatic_checks") or {}).get("spoiler_guard"),
        ),
        "context_understanding": pending(
            followup_context_replayed=any(item.get("context_replayed") is True for item in audit),
            previous_decision_included=any(item.get("previous_decision_included") is True for item in audit),
        ),
        "domain_judgment": pending(core30_automatic_status=quality_gate.get("status")),
        "tool_judgment": pending(
            lookup_selection=checks.get("lookup_selection"),
            actual_lookup_tools=lookup.get("executed_tools") or [],
        ),
        "observation_interpretation": (
            pending(
                initial_actions=initial.get("actions"),
                followup_actions=followup.get("actions"),
                tool_result_present=bool(lookup),
            ) if observation_applicable else {"status": "NOT_APPLICABLE", "reason": "NO_TOOL_OBSERVATION"}
        ),
        "structured_output_stability": {
            "status": structured_status,
            "first_pass_contract_count": sum(
                item.get("raw_contract_valid") is True for item in audit if item.get("stage") == "LLM_CONTRACT"
            ),
            "repair_call_count": metrics.get("repair_call_count"),
            "format_fallback_count": metrics.get("format_fallback_count"),
        },
        "decision_consistency": pending(
            structural_check=checks.get("processing_vs_final_guidance_structure"),
            initial_actions=initial.get("actions"),
            followup_actions=followup.get("actions"),
        ),
        "efficiency": {
            "status": "MEASURED_NO_QUALITY_OFFSET",
            "metrics": {
                key: metrics.get(key) for key in (
                    "decision_stage_count", "provider_call_count", "repair_call_count",
                    "format_fallback_count", "tool_call_count", "input_tokens", "output_tokens",
                    "total_tokens", "reasoning_tokens", "cached_tokens", "cache_write_tokens",
                    "provider_cost_usd", "case_latency_ms", "tool_latency_ms", "validation_latency_ms",
                )
            },
        },
        "review_record": {
            "status": "PENDING_REVIEW",
            "reviewer": "",
            "ratings": {axis: None for axis in HUMAN_AXES},
            "evidence": {axis: "" for axis in HUMAN_AXES},
            "hard_fail_triggered": None,
            "hard_fail_evidence": "",
        },
    }
    return scorecard


def scorecard_counts(results: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, dict[str, int]] = {}
    for axis in SCORECARD_AXES:
        statuses: dict[str, int] = {}
        for result in results:
            status = (result.get("project_model_capability_scorecard") or {}).get(axis, {}).get("status") or "NOT_AVAILABLE"
            statuses[status] = statuses.get(status, 0) + 1
        counts[axis] = statuses
    return {"axes": counts, "cases": len(results), "human_reviewed_cases": sum(
        (result.get("project_model_capability_scorecard") or {}).get("review_record", {}).get("status") == "REVIEWED"
        for result in results
    )}
