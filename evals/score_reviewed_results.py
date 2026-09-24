"""Aggregate team-reviewed core-30 outputs; optionally publish numeric Langfuse scores.

The input is a copy of one run_llm_eval.py JSON result after reviewers fill each
project_model_capability_scorecard.review_record. Never sends raw review evidence.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / ".env", override=False)

from evals.model_selection_scorecard import HUMAN_AXES, RATINGS
from backend.services.langfuse_service import record_evaluation_score, record_event, trace_id_for_seed


def score_reviewed(document: dict[str, Any]) -> dict[str, Any]:
    summary = document.get("summary") or {}
    results = document.get("results") or []
    errors: list[str] = []
    ids = [result.get("id") for result in results if isinstance(result, dict)]
    if len(results) != 30 or len(ids) != len(results) or not all(type(value) is int for value in ids) or sorted(ids) != list(range(1, 31)):
        errors.append("CORE30_IDS_MUST_BE_EXACTLY_1_TO_30")
    run_id = summary.get("evaluation_run_id")
    dataset_sha = summary.get("dataset_sha256")
    contract_sha = summary.get("quality_contract_sha256")
    model = summary.get("model")
    started_at = summary.get("evaluation_started_at")
    if not all(isinstance(value, str) and value for value in (run_id, dataset_sha, contract_sha, model, started_at)):
        errors.append("RUN_PROVENANCE_INCOMPLETE")
    if summary.get("observability_complete") is not True:
        errors.append("LANGFUSE_CASE_EXPORT_NOT_CONFIRMED")
    if summary.get("completed_rows") != 30 or summary.get("failed_rows") != 0:
        errors.append("INCOMPLETE_EXECUTION")
    if summary.get("hard_fail_auto_cases") != 0:
        errors.append("AUTOMATIC_HARD_FAIL_PRESENT")

    axis_values: dict[str, list[float]] = {axis: [] for axis in HUMAN_AXES}
    pending_cases: list[int] = []
    failed_cases: list[int] = []
    hard_fail_cases: list[int] = []
    contract_pass = 0
    for result in results:
        if not isinstance(result, dict):
            continue
        case_id = result.get("id")
        label = f"CASE_{case_id}"
        if any(result.get(key) != summary.get(key) for key in (
            "evaluation_run_id", "dataset_sha256", "quality_contract_sha256", "model"
        )):
            errors.append(f"{label}_PROVENANCE_MISMATCH")
        seed = result.get("trace_seed")
        if not isinstance(seed, str) or not seed or result.get("langfuse_trace_id") != trace_id_for_seed(seed):
            errors.append(f"{label}_TRACE_MISMATCH")
        card = result.get("project_model_capability_scorecard") or {}
        contract_ok = card.get("structured_output_stability", {}).get("status") == "PASS"
        contract_pass += contract_ok
        auto_status = result.get("quality_contract_gate", {}).get("status")
        review = card.get("review_record") or {}
        ratings = review.get("ratings") or {}
        evidence = review.get("evidence") or {}
        applicable = []
        reviewed = review.get("status") == "REVIEWED" and bool(str(review.get("reviewer") or "").strip())
        for axis in HUMAN_AXES:
            if axis == "observation_interpretation" and card.get(axis, {}).get("status") == "NOT_APPLICABLE":
                if ratings.get(axis) not in (None, "NOT_APPLICABLE"):
                    errors.append(f"{label}_{axis}_MUST_BE_NOT_APPLICABLE")
                continue
            applicable.append(axis)
            rating = ratings.get(axis)
            if rating not in RATINGS or not str(evidence.get(axis) or "").strip():
                reviewed = False
            else:
                axis_values[axis].append(RATINGS[rating])
        if review.get("hard_fail_triggered") is not False:
            if review.get("hard_fail_triggered") is True:
                hard_fail_cases.append(case_id)
                if not str(review.get("hard_fail_evidence") or "").strip():
                    errors.append(f"{label}_HARD_FAIL_EVIDENCE_REQUIRED")
            else:
                reviewed = False
        if not reviewed:
            pending_cases.append(case_id)
        if (
            result.get("execution_status") != "COMPLETED" or not contract_ok
            or auto_status not in {"PASS", "REVIEW_REQUIRED"}
            or result.get("quality_contract_gate", {}).get("hard_fail_auto") is True
            or any(ratings.get(axis) != "PASS" for axis in applicable)
        ):
            failed_cases.append(case_id)

    if errors:
        status = "INVALID"
    elif pending_cases:
        status = "AWAITING_REVIEW"
    elif hard_fail_cases or failed_cases or contract_pass != 30:
        status = "QUALITY_FAIL"
    else:
        status = "QUALITY_PASS"
    return {
        "status": status,
        "evaluation_run_id": run_id,
        "selection_run_id": summary.get("selection_run_id"),
        "dataset_sha256": dataset_sha,
        "quality_contract_sha256": contract_sha,
        "model": model,
        "cases": len(results),
        "reviewed_cases": len(results) - len(pending_cases),
        "pending_case_ids": pending_cases,
        "nonpassing_case_ids": failed_cases,
        "human_hard_fail_case_ids": hard_fail_cases,
        "final_contract_pass_cases": contract_pass,
        "axis_mean": {
            axis: round(sum(values) / len(values), 4) if values and not pending_cases else None
            for axis, values in axis_values.items()
        },
        "efficiency": {
            key: summary.get(key) for key in (
                "provider_call_count", "provider_cost_usd_reported", "latency_p50_ms", "latency_p95_ms"
            )
        },
        "errors": errors,
        "rule": "Human evidence and all applicable axis ratings must be complete; PARTIAL is not PASS.",
    }


def publish_reviewed(document: dict[str, Any], scored: dict[str, Any]) -> bool:
    if scored["status"] not in {"QUALITY_PASS", "QUALITY_FAIL"}:
        return False
    summary = document["summary"]
    for result in document["results"]:
        card = result["project_model_capability_scorecard"]
        ratings = card["review_record"]["ratings"]
        for axis in HUMAN_AXES:
            if axis == "observation_interpretation" and card[axis]["status"] == "NOT_APPLICABLE":
                continue
            if not record_evaluation_score(
                trace_seed=result["trace_seed"], name=axis, value=RATINGS[ratings[axis]],
                evaluation_started_at=summary["evaluation_started_at"],
                evaluation_run_id=summary["evaluation_run_id"], case_id=result["id"],
                dataset_sha256=summary["dataset_sha256"], model=summary["model"],
            ):
                return False
    return record_event("evaluation_review_summary", {
        "evaluation_name": "core30-reviewed",
        "evaluation_run_id": summary["evaluation_run_id"],
        "selection_run_id": summary.get("selection_run_id"),
        "dataset_sha256": summary["dataset_sha256"],
        "quality_contract_sha256": summary["quality_contract_sha256"],
        "quality_status": scored["status"],
        "llm_model": summary["model"],
    })


def write_review_csv(path: Path, document: dict[str, Any], scored: dict[str, Any]) -> None:
    """팀 공유용 숫자 판정표. 원문 응답과 사례별 근거 문장은 내보내지 않는다."""
    if scored["status"] == "INVALID":
        raise ValueError("INVALID_REVIEW_CANNOT_EXPORT")
    fields = (
        "selection_run_id", "evaluation_run_id", "dataset_sha256", "model", "case_id",
        "langfuse_trace_id", "review_status", *HUMAN_AXES, "structured_output_stability",
        "core30_auto_contract", "human_hard_fail", "quality_gate",
    )
    summary = document["summary"]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in document["results"]:
            card = result["project_model_capability_scorecard"]
            review = card["review_record"]
            writer.writerow({
                "selection_run_id": summary.get("selection_run_id"),
                "evaluation_run_id": summary["evaluation_run_id"],
                "dataset_sha256": summary["dataset_sha256"],
                "model": summary["model"],
                "case_id": result["id"],
                "langfuse_trace_id": result["langfuse_trace_id"],
                "review_status": review.get("status"),
                **{axis: (review.get("ratings") or {}).get(axis) for axis in HUMAN_AXES},
                "structured_output_stability": card["structured_output_stability"]["status"],
                "core30_auto_contract": result["quality_contract_gate"]["status"],
                "human_hard_fail": review.get("hard_fail_triggered"),
                "quality_gate": scored["status"],
            })


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Reviewed copy of a single model JSON result")
    parser.add_argument("--output", required=True, help="Local score summary JSON")
    parser.add_argument("--csv-output", help="Safe per-case rating CSV; no raw text or evidence")
    parser.add_argument("--publish-langfuse", action="store_true", help="Publish only numeric scores, no evidence/text")
    args = parser.parse_args()
    document = json.loads(Path(args.input).read_text(encoding="utf-8"))
    scored = score_reviewed(document)
    if args.csv_output and scored["status"] != "INVALID":
        write_review_csv(Path(args.csv_output), document, scored)
        scored["csv_output"] = args.csv_output
    if args.publish_langfuse:
        scored["langfuse_review_export"] = "PASS" if publish_reviewed(document, scored) else "FAILED_OR_NOT_READY"
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(scored, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(scored, ensure_ascii=False, indent=2))
    if scored["status"] == "INVALID" or scored.get("langfuse_review_export") == "FAILED_OR_NOT_READY":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
