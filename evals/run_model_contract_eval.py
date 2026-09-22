"""실제 모델의 정규화 전/후 계약 준수 측정 도구.

기본값은 외부 호출 미실행이다. --allow-external-llm을 명시하고, 필요한 수의 입력 데이터가
준비된 경우에만 호출한다. 이 도구는 언어/도메인 정답을 생성하거나 품질을 판정하지 않는다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas import AgentContext
from backend.services.domain_skill import build_llm_skill_context
from backend.services.llm import analyze_user_request
from evals.run_llm_eval import _message, _observability_export, load_rows


def _context(case_id: str) -> AgentContext:
    return AgentContext(
        session_id=f"contract-session-{case_id}",
        team_id=f"contract-team-{case_id}",
        theme_id="contract-eval",
        current_puzzle_id="contract-p01",
        requested_puzzle_id="contract-p01",
        remaining_time_minutes=30,
        puzzle_context={"title": "계약 평가용 퍼즐 맥락"},
        recent_turns=[],
        domain_skill=build_llm_skill_context(),
        tool_results={},
    )


def _contract_report(audit: list[dict[str, Any]]) -> dict[str, Any] | None:
    for item in reversed(audit):
        if item.get("stage") == "LLM_CONTRACT" and item.get("llm_stage") == "INITIAL":
            return item
    return None


def run(
    dataset: Path,
    output: Path,
    *,
    required_cases: int = 100,
    allow_external_llm: bool = False,
    retry_invalid_contract: bool = False,
    allow_observability_export: bool = False,
) -> dict[str, Any]:
    rows = load_rows(dataset)
    planned = min(len(rows), required_cases)

    if not allow_external_llm:
        summary = {
            "status": "NOT_RUN_EXTERNAL_LLM_APPROVAL_REQUIRED",
            "dataset": str(dataset),
            "required_cases": required_cases,
            "available_cases": len(rows),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"summary": summary, "results": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    if len(rows) < required_cases:
        summary = {
            "status": "NOT_RUN_INSUFFICIENT_EVAL_INPUTS",
            "dataset": str(dataset),
            "required_cases": required_cases,
            "available_cases": len(rows),
            "note": "횟수를 맞추기 위해 새 도메인 입력/정답을 자동 생성하지 않음",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"summary": summary, "results": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    results: list[dict[str, Any]] = []
    first_raw_valid = 0
    normalized_success = 0
    retry_attempted = 0
    retry_raw_valid = 0
    failed = 0

    with _observability_export(allow_observability_export):
        for index, row in enumerate(rows[:required_cases], 1):
            case_id = str(row.get("id", index))
            audit: list[dict[str, Any]] = []
            try:
                result = analyze_user_request(
                    _message(row),
                    _context(case_id),
                    provider="openrouter",
                    request_id=f"contract_{case_id}_attempt1",
                    audit=audit,
                )
                report = _contract_report(audit) or {}
                raw_ok = bool(report.get("raw_contract_valid"))
                first_raw_valid += raw_ok
                normalized_success += 1

                retry_report = None
                retry_result = None
                if retry_invalid_contract and not raw_ok:
                    retry_attempted += 1
                    retry_audit: list[dict[str, Any]] = []
                    retry_result_obj = analyze_user_request(
                        _message(row),
                        _context(case_id),
                        provider="openrouter",
                        request_id=f"contract_{case_id}_attempt2",
                        audit=retry_audit,
                    )
                    retry_report = _contract_report(retry_audit) or {}
                    retry_raw_valid += bool(retry_report.get("raw_contract_valid"))
                    retry_result = retry_result_obj.model_dump(mode="json")

                results.append(
                    {
                        "id": row.get("id", case_id),
                        "execution_status": "COMPLETED",
                        "first_attempt": {
                            "raw_contract_valid": report.get("raw_contract_valid"),
                            "raw_contract_errors": report.get("raw_contract_errors", []),
                            "normalization_changed_fields": report.get("normalization_changed_fields", []),
                            "normalized_output": result.model_dump(mode="json"),
                        },
                        "retry_attempted": retry_report is not None,
                        "retry_attempt": (
                            {
                                "raw_contract_valid": retry_report.get("raw_contract_valid"),
                                "raw_contract_errors": retry_report.get("raw_contract_errors", []),
                                "normalization_changed_fields": retry_report.get("normalization_changed_fields", []),
                                "normalized_output": retry_result,
                            }
                            if retry_report is not None
                            else None
                        ),
                    }
                )
            except Exception as exc:
                failed += 1
                results.append(
                    {
                        "id": row.get("id", case_id),
                        "execution_status": "FAILED",
                        "error_type": type(exc).__name__,
                    }
                )

    summary = {
        "status": "COMPLETED_WITH_FAILURES" if failed else "COMPLETED",
        "dataset": str(dataset),
        "provider": "openrouter",
        "cases": planned,
        "failed_cases": failed,
        "first_attempt_raw_contract_valid": first_raw_valid,
        "first_attempt_raw_contract_valid_rate": first_raw_valid / planned if planned else None,
        "normalized_parse_success": normalized_success,
        "normalized_parse_success_rate": normalized_success / planned if planned else None,
        "retry_invalid_contract_enabled": retry_invalid_contract,
        "retry_attempted": retry_attempted,
        "retry_raw_contract_valid": retry_raw_valid,
        "retry_raw_contract_valid_rate": retry_raw_valid / retry_attempted if retry_attempted else None,
        "note": "정규화 기술 계약 측정이며 도메인 의미 품질 점수가 아님",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/dataset.jsonl")
    parser.add_argument("--output", default="evals/results/model_contract_100.json")
    parser.add_argument("--required-cases", type=int, default=100)
    parser.add_argument("--allow-external-llm", action="store_true")
    parser.add_argument("--retry-invalid-contract", action="store_true")
    parser.add_argument("--allow-observability-export", action="store_true")
    args = parser.parse_args()
    summary = run(
        Path(args.dataset),
        Path(args.output),
        required_cases=args.required_cases,
        allow_external_llm=args.allow_external_llm,
        retry_invalid_contract=args.retry_invalid_contract,
        allow_observability_export=args.allow_observability_export,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
