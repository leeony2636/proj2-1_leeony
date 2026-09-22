"""실제 서비스 흐름 기준 LLM 평가 실행기.

평가 경로:
고객 발화 -> LLM INITIAL -> 선택 조회 -> LLM FOLLOWUP -> 코드 검증/격리 처리 -> 최종 안내

- 세션/MCP/운영 요청은 평가 전용 MemoryRuntime에 격리한다.
- provider=openrouter는 외부 호출이므로 --allow-external-llm 없이는 실행하지 않는다.
- Langfuse 외부 전송은 기본 차단하며 --allow-observability-export 때만 허용한다.
- 현재 dataset.jsonl의 합성/과거 seed를 사람 Ground Truth로 간주하지 않는다.
- 자동 판정이 어려운 질문 적절성, 규칙의 의미상 올바른 적용, 직원 전달의 사실성은 사람 검토로 남긴다.
"""
from __future__ import annotations

import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import sys
from typing import Any, Iterator

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.schemas import AgentRequest, AgentResponse, AgentStatus
from backend.services import agent_orchestrator
from backend.services.langfuse_service import record_event
from evals.evaluation_runtime import EvaluationMCPClient, isolated_agent_runtime


DEFAULT_EVAL_THEME = "last_train"


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"INVALID_JSONL:{path}:{line_no}") from exc
    return rows


def _message(row: dict[str, Any]) -> str:
    input_data = row.get("input") or {}
    value = input_data.get("utterance") or row.get("utterance")
    if not value:
        raise ValueError(f"EVAL_UTTERANCE_MISSING:{row.get('id')}")
    return str(value)


def _safe_case_id(row: dict[str, Any], index: int) -> str:
    raw = str(row.get("id", index))
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in raw)[:80]


def _last_stage(audit: list[dict[str, Any]], stage: str) -> dict[str, Any] | None:
    for item in reversed(audit):
        if item.get("stage") == stage:
            return item
    return None


def _all_stages(audit: list[dict[str, Any]], stage: str) -> list[dict[str, Any]]:
    return [item for item in audit if item.get("stage") == stage]


def _seed_case(client: EvaluationMCPClient, row: dict[str, Any], index: int) -> AgentRequest:
    setup = row.get("eval_setup") or {}
    context = row.get("context") or {}
    input_data = row.get("input") or {}
    case_id = _safe_case_id(row, index)

    theme_id = str(setup.get("theme_id") or context.get("theme_id") or DEFAULT_EVAL_THEME)
    team_id = str(setup.get("team_id") or f"eval-team-{case_id}")
    session_data = client.create_session(theme_id, team_id)
    session_id = str(session_data["session_id"])

    remaining = setup.get("remaining_time_minutes")
    if remaining is None:
        remaining = context.get("remaining_time_minutes", input_data.get("remaining_time_minutes"))
    if remaining is not None:
        client.set_remaining_time(session_id, float(remaining))

    requested_puzzle_id = setup.get("current_puzzle_id") or context.get("current_puzzle_id")
    if requested_puzzle_id:
        client.set_current_puzzle(session_id, str(requested_puzzle_id))

    session_now = client.get_session(session_id)
    puzzle_id = str(session_now["current_puzzle_id"]) if session_now.get("current_puzzle_id") else None

    recent_turns = setup.get("recent_turns") or context.get("recent_turns") or []
    for turn in recent_turns:
        role = str(turn.get("role", "user"))
        if role not in {"user", "assistant"}:
            continue
        content = str(turn.get("content", ""))
        if content:
            client.record_conversation_turn(session_id, role, content, f"eval-seed-turn-{case_id}")

    for hint in setup.get("hint_history") or []:
        target_puzzle = str(hint.get("puzzle_id") or puzzle_id or "")
        if not target_puzzle:
            continue
        client.seed_hint(
            session_id,
            team_id,
            target_puzzle,
            str(hint.get("strength", "WEAK")),
            str(hint.get("reason", "EVAL_SEED")),
        )

    for master in setup.get("master_requests") or []:
        client.seed_master_request(
            session_id,
            team_id,
            str(master.get("reason", "EVAL_SEED_MASTER_REQUEST")),
            str(master.get("status", "OPEN")),
        )

    return AgentRequest(
        request_id=f"eval_{case_id}",
        session_id=session_id,
        team_id=team_id,
        message=_message(row),
        puzzle_id=puzzle_id,
    )


def _processing_consistency(response: AgentResponse) -> tuple[bool, list[str]]:
    """의미 품질이 아니라 '실제 처리 결과와 안내'의 구조적 모순만 검사한다."""
    problems: list[str] = []
    message = response.customer_message or ""
    completed = {item.value for item in response.completed_actions}

    if "직원 확인 요청이 접수되었습니다." in message and not response.master_request_ids:
        problems.append("MESSAGE_CLAIMS_MASTER_REQUEST_WITHOUT_REQUEST_ID")
    if "승인된 힌트를 제공할 수 있습니다." in message and not response.hint_text:
        problems.append("MESSAGE_CLAIMS_HINT_WITHOUT_APPROVED_HINT_TEXT")
    if response.status == AgentStatus.MASTER_REQUEST and not response.master_request_ids:
        problems.append("MASTER_REQUEST_STATUS_WITHOUT_REQUEST")
    if response.status == AgentStatus.PROVIDE_HINT and not response.hint_text:
        problems.append("PROVIDE_HINT_STATUS_WITHOUT_HINT")
    if response.status == AgentStatus.ANSWER_CONFIRMATION_REQUIRED and not (
        response.requires_confirmation and response.offer_id
    ):
        problems.append("ANSWER_CONFIRMATION_STATUS_WITHOUT_OFFER")
    if "REPORT_EQUIPMENT" in completed and not response.master_request_ids:
        problems.append("EQUIPMENT_ACTION_WITHOUT_STAFF_REQUEST")
    if "REQUEST_GAME_MASTER" in completed and not response.master_request_ids:
        problems.append("MASTER_ACTION_WITHOUT_STAFF_REQUEST")
    return not problems, problems


def _expected_service(row: dict[str, Any]) -> dict[str, Any]:
    """사람이 명시적으로 서비스 흐름 정답으로 확정한 필드만 사용한다."""
    if not row.get("human_validated"):
        return {}
    expected = row.get("service_expected")
    return expected if isinstance(expected, dict) else {}


def _evaluate_case(
    row: dict[str, Any],
    response: AgentResponse,
    audit: list[dict[str, Any]],
    master_requests: list[dict[str, Any]],
) -> dict[str, Any]:
    initial = _last_stage(audit, "INITIAL_DECISION") or {}
    followup = _last_stage(audit, "FOLLOWUP_DECISION") or {}
    lookup = _last_stage(audit, "LOOKUP_RESULTS") or {}
    expected = _expected_service(row)

    automatic_checks: dict[str, dict[str, Any]] = {}
    consistent, problems = _processing_consistency(response)
    automatic_checks["processing_vs_final_guidance_structure"] = {
        "status": "PASS" if consistent else "FAIL",
        "problems": problems,
    }

    actual_lookup = list(lookup.get("executed_tools") or [])
    if "lookup_tools" in expected:
        automatic_checks["lookup_selection"] = {
            "status": "PASS" if sorted(actual_lookup) == sorted(expected["lookup_tools"]) else "FAIL",
            "expected": expected["lookup_tools"],
            "actual": actual_lookup,
        }
    else:
        automatic_checks["lookup_selection"] = {
            "status": "NOT_SCORED_NO_HUMAN_EXPECTED",
            "actual": actual_lookup,
        }

    actual_actions = [item.value for item in response.completed_actions]
    if "completed_actions" in expected:
        automatic_checks["final_actions"] = {
            "status": "PASS" if sorted(actual_actions) == sorted(expected["completed_actions"]) else "FAIL",
            "expected": expected["completed_actions"],
            "actual": actual_actions,
        }
    else:
        automatic_checks["final_actions"] = {
            "status": "NOT_SCORED_NO_HUMAN_EXPECTED",
            "actual": actual_actions,
        }

    if "final_status" in expected:
        automatic_checks["final_status"] = {
            "status": "PASS" if response.status.value == expected["final_status"] else "FAIL",
            "expected": expected["final_status"],
            "actual": response.status.value,
        }
    else:
        automatic_checks["final_status"] = {
            "status": "NOT_SCORED_NO_HUMAN_EXPECTED",
            "actual": response.status.value,
        }

    lookup_changed_behavior = None
    if initial and followup:
        lookup_changed_behavior = any(
            initial.get(field) != followup.get(field)
            for field in ("actions", "needs_clarification", "support_need", "intent")
        )
    automatic_checks["lookup_result_behavior_change"] = {
        "status": "OBSERVED_NOT_SCORED" if lookup_changed_behavior is not None else "NOT_APPLICABLE",
        "changed": lookup_changed_behavior,
        "initial_actions": initial.get("actions"),
        "followup_actions": followup.get("actions"),
    }

    clarification = followup.get("clarifying_question") or initial.get("clarifying_question")
    handoff_rows = [item for item in master_requests if str(item.get("reason", "")).startswith("EQUIPMENT_ISSUE:") or item.get("reason")]
    reported_rules = list((followup or initial).get("reported_applied_skill_rules") or [])
    human_review = {
        "question_appropriateness": {
            "status": "REVIEW_REQUIRED" if clarification else "NOT_APPLICABLE",
            "question": clarification,
        },
        "staff_handoff_factuality": {
            "status": "REVIEW_REQUIRED" if handoff_rows else "NOT_APPLICABLE",
            "handoff_texts": [str(item.get("reason", "")) for item in handoff_rows[-3:]],
        },
        "domain_skill_application_correctness": {
            "status": "REVIEW_REQUIRED" if reported_rules else "NOT_APPLICABLE",
            "llm_reported_rule_ids": reported_rules,
            "note": "rule id 존재/보고 여부와 실제 올바른 규칙 적용은 별개",
        },
        "final_guidance_semantic_consistency": {
            "status": "REVIEW_REQUIRED" if response.status != AgentStatus.ERROR else "NOT_APPLICABLE",
            "customer_message": response.customer_message,
        },
    }

    contract_reports = _all_stages(audit, "LLM_CONTRACT")
    return {
        "automatic_checks": automatic_checks,
        "human_review": human_review,
        "contract_reports": contract_reports,
    }


@contextmanager
def _observability_export(enabled: bool) -> Iterator[None]:
    """평가 기본값은 외부 Langfuse 쓰기 차단. 명시 옵션일 때만 기존 환경을 사용한다."""
    if enabled:
        yield
        return
    keys = ["LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY"]
    old = {key: os.environ.get(key) for key in keys}
    try:
        for key in keys:
            os.environ.pop(key, None)
        yield
    finally:
        for key, value in old.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def run(
    dataset: Path,
    provider: str,
    output: Path,
    *,
    limit: int | None = None,
    allow_external_llm: bool = False,
    allow_observability_export: bool = False,
) -> dict[str, Any]:
    rows = load_rows(dataset)
    if limit is not None:
        rows = rows[: max(limit, 0)]

    if provider != "baseline" and not allow_external_llm:
        summary = {
            "status": "NOT_RUN_EXTERNAL_LLM_APPROVAL_REQUIRED",
            "dataset": str(dataset),
            "provider": provider,
            "rows_planned": len(rows),
            "note": "실제 Provider 호출은 --allow-external-llm 명시 전에는 실행하지 않음",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"summary": summary, "results": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    results: list[dict[str, Any]] = []
    failed = 0
    completed = 0
    auto_scored = 0
    auto_passed = 0
    raw_contract_reports = 0
    raw_contract_valid = 0
    normalization_changed = 0

    with _observability_export(allow_observability_export):
        for index, row in enumerate(rows, 1):
            case_id = _safe_case_id(row, index)
            audit: list[dict[str, Any]] = []
            try:
                with isolated_agent_runtime() as client:
                    request = _seed_case(client, row, index)
                    response = agent_orchestrator.handle_agent_request(
                        request,
                        llm_provider=provider,
                        evaluation_audit=audit,
                    )
                    master_requests = client.master_request_status(request.session_id, request.team_id, limit=20)
                    case_eval = _evaluate_case(row, response, audit, master_requests)

                    for check in case_eval["automatic_checks"].values():
                        if check.get("status") in {"PASS", "FAIL"}:
                            auto_scored += 1
                            auto_passed += check["status"] == "PASS"
                    for contract in case_eval["contract_reports"]:
                        raw_contract_reports += 1
                        raw_contract_valid += bool(contract.get("raw_contract_valid"))
                        normalization_changed += bool(contract.get("normalization_changed_fields"))

                    completed += 1
                    results.append(
                        {
                            "id": row.get("id", case_id),
                            "execution_status": "COMPLETED",
                            "provider": provider,
                            "evaluation_mode": (
                                "REAL_LLM_ISOLATED_SERVICE_FLOW" if provider != "baseline" else "BASELINE_ISOLATED_SERVICE_FLOW"
                            ),
                            "human_validated": bool(row.get("human_validated")),
                            "response": response.model_dump(mode="json"),
                            "trace": audit,
                            "master_requests": master_requests,
                            **case_eval,
                        }
                    )
            except Exception as exc:
                failed += 1
                results.append(
                    {
                        "id": row.get("id", case_id),
                        "execution_status": "FAILED",
                        "provider": provider,
                        "error_type": type(exc).__name__,
                        "trace": audit,
                        "automatic_checks": {},
                        "human_review": {"failure_analysis": {"status": "REVIEW_REQUIRED"}},
                    }
                )

    summary = {
        "status": "COMPLETED_WITH_FAILURES" if failed else "COMPLETED",
        "dataset": str(dataset),
        "provider": provider,
        "evaluation_mode": (
            "REAL_LLM_ISOLATED_SERVICE_FLOW" if provider != "baseline" else "BASELINE_ISOLATED_SERVICE_FLOW"
        ),
        "rows": len(rows),
        "completed_rows": completed,
        "failed_rows": failed,
        "automatic_scored_checks": auto_scored,
        "automatic_passed_checks": auto_passed,
        "automatic_pass_rate": (auto_passed / auto_scored if auto_scored else None),
        "raw_model_contract_reports": raw_contract_reports,
        "raw_model_contract_valid": raw_contract_valid,
        "raw_model_contract_valid_rate": (raw_contract_valid / raw_contract_reports if raw_contract_reports else None),
        "rows_with_normalization_changes": normalization_changed,
        "domain_quality_rate": None,
        "note": (
            "평가 세션/MCP/부작용은 MemoryRuntime에 격리. 합성/미검증 row는 도메인 품질 점수로 집계하지 않으며 "
            "질문 적절성·직원 전달 사실성·Skill 규칙의 올바른 적용·최종 안내 의미 일치는 사람 검토 대상."
        ),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")

    if allow_observability_export:
        record_event(
            "evaluation_run",
            {
                "evaluation_name": dataset.name,
                "evaluation_score": summary["automatic_pass_rate"],
                "llm_provider": provider,
            },
        )
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/dataset.jsonl")
    parser.add_argument("--provider", choices=["baseline", "openrouter"], required=True)
    parser.add_argument("--output", default="evals/results/latest_service_flow.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--allow-external-llm",
        action="store_true",
        help="OpenRouter 같은 실제 Provider 호출을 명시적으로 허용한다. 비용/외부 전송 가능성을 확인한 뒤 사용한다.",
    )
    parser.add_argument(
        "--allow-observability-export",
        action="store_true",
        help="평가 관측 이벤트를 설정된 Langfuse로 전송한다. 기본값은 외부 쓰기 차단이다.",
    )
    args = parser.parse_args()

    output = Path(args.output)
    summary = run(
        Path(args.dataset),
        args.provider,
        output,
        limit=args.limit,
        allow_external_llm=args.allow_external_llm,
        allow_observability_export=args.allow_observability_export,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
