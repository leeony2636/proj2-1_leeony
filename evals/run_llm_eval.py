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
import csv
import hashlib
from contextlib import contextmanager
import json
import os
from pathlib import Path
import statistics
import sys
import time
from typing import Any, Iterator
from datetime import datetime, timezone
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

# 로컬 VS Code/PowerShell 실행 시 .env를 읽되, 이미 설정된 환경변수는 덮어쓰지 않는다.
load_dotenv(ROOT / ".env", override=False)

from backend.schemas import AgentRequest, AgentResponse, AgentStatus
from backend.services import agent_orchestrator
from backend.services.langfuse_service import record_event, record_evaluation_score, trace_id_for_seed
from evals.evaluation_runtime import EvaluationMCPClient, isolated_agent_runtime
from evals.model_selection_scorecard import build_scorecard, scorecard_counts


DEFAULT_EVAL_THEME = "last_train"
PROJECT_TEST_BUDGET_USD = 30.0
MODEL_SELECTION_TOTAL_BUDGET_USD = 5.0
DEFAULT_QUALITY_CONTRACT = ROOT / "evals/core30_quality_contract.json"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _evaluation_code_fingerprint() -> str:
    """평가기와 실행 경계의 현재 코드 버전을 로컬 hash로 고정한다."""
    digest = hashlib.sha256()
    for rel in (
        "evals/run_llm_eval.py",
        "evals/evaluation_runtime.py",
        "backend/services/agent_orchestrator.py",
        "backend/services/llm_contract.py",
        "mcp_server/contract_dispatch.py",
    ):
        path = ROOT / rel
        digest.update(rel.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


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


def _seed_case(client: EvaluationMCPClient, row: dict[str, Any], index: int, run_id: str) -> AgentRequest:
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

    precondition = input_data.get("precondition") if isinstance(input_data.get("precondition"), dict) else {}
    recent_turns = list(setup.get("recent_turns") or context.get("recent_turns") or [])
    previous_utterance = str(precondition.get("previous_utterance") or "").strip()
    if previous_utterance:
        recent_turns.append({"role": "user", "content": previous_utterance})
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

    master_rows = list(setup.get("master_requests") or [])
    precondition_status = str(precondition.get("master_request_status") or "").strip().upper()
    if precondition_status:
        master_rows.append({
            "reason": "EVAL_PRECONDITION_MASTER_REQUEST",
            "status": precondition_status,
        })
    for master in master_rows:
        client.seed_master_request(
            session_id,
            team_id,
            str(master.get("reason", "EVAL_SEED_MASTER_REQUEST")),
            str(master.get("status", "OPEN")),
        )

    return AgentRequest(
        request_id=f"eval_{run_id}_{case_id}",
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


def _load_quality_contract(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("cases"), dict):
        raise ValueError("INVALID_QUALITY_CONTRACT")
    return data


def _quality_contract_checks(
    quality_case: dict[str, Any],
    response: AgentResponse,
    audit: list[dict[str, Any]],
) -> dict[str, Any]:
    """Evaluator 전용 계약을 실제 결과와 비교한다. 이 함수의 값은 Agent 입력에 전달되지 않는다."""
    initial = _last_stage(audit, "INITIAL_DECISION") or {}
    followup = _last_stage(audit, "FOLLOWUP_DECISION") or {}
    decision = followup or initial
    lookup = _last_stage(audit, "LOOKUP_RESULTS") or {}
    actual_lookup = list(lookup.get("executed_tools") or [])
    actual_actions = [item.value for item in response.completed_actions]
    checks: dict[str, dict[str, Any]] = {}

    expected_support = quality_case.get("support_need")
    if expected_support:
        actual_support = decision.get("support_need")
        checks["support_need"] = {
            "status": "PASS" if actual_support == expected_support else "FAIL",
            "expected": expected_support,
            "actual": actual_support,
        }

    required_lookup = list(quality_case.get("required_lookup_tools") or [])
    if required_lookup:
        checks["required_lookup_tools"] = {
            "status": "PASS" if all(item in actual_lookup for item in required_lookup) else "FAIL",
            "expected": required_lookup,
            "actual": actual_lookup,
        }

    required_actions = list(quality_case.get("required_actions") or [])
    if required_actions:
        checks["required_actions"] = {
            "status": "PASS" if all(item in actual_actions for item in required_actions) else "FAIL",
            "expected": required_actions,
            "actual": actual_actions,
        }

    forbidden_actions = list(quality_case.get("forbidden_actions") or [])
    if forbidden_actions:
        present = [item for item in forbidden_actions if item in actual_actions]
        checks["forbidden_actions"] = {
            "status": "PASS" if not present else "FAIL",
            "forbidden": forbidden_actions,
            "actual_forbidden_present": present,
        }

    allowed_status = list(quality_case.get("allowed_status") or [])
    if allowed_status:
        checks["final_status"] = {
            "status": "PASS" if response.status.value in allowed_status else "FAIL",
            "allowed": allowed_status,
            "actual": response.status.value,
        }

    if quality_case.get("requires_clarification") is True:
        clarification = bool(decision.get("needs_clarification")) or "ASK_CLARIFICATION" in [
            item.value for item in response.pending_actions
        ]
        checks["requires_clarification"] = {
            "status": "PASS" if clarification else "FAIL",
            "actual": clarification,
        }

    hard_fail_auto = response.spoiler_guard != "ANSWERVAULT_SEPARATED"
    checks["spoiler_guard"] = {
        "status": "FAIL" if hard_fail_auto else "PASS",
        "actual": response.spoiler_guard,
    }

    failed = [name for name, value in checks.items() if value.get("status") == "FAIL"]
    needs_human = bool(quality_case.get("human_review_required"))
    if failed:
        status = "FAIL"
    elif needs_human:
        status = "REVIEW_REQUIRED"
    else:
        status = "PASS"
    return {
        "status": status,
        "failed_checks": failed,
        "automatic_checks": checks,
        "human_review_required": needs_human,
        "expected_description": quality_case.get("expected_description"),
        "hard_fail_auto": hard_fail_auto,
        "note": "평가계약은 응답 생성 뒤에만 사용하며 Agent prompt/context에는 전달하지 않는다.",
    }


def _sum_known(records: list[dict[str, Any]], key: str) -> tuple[int | float | None, bool]:
    values = [record.get(key) for record in records]
    known = [value for value in values if isinstance(value, (int, float))]
    return (sum(known) if known else None, len(known) == len(records) if records else True)


def _case_metrics(audit: list[dict[str, Any]], case_latency_ms: float) -> dict[str, Any]:
    successful_calls = _all_stages(audit, "LLM_PROVIDER_CALL")
    failed_calls = _all_stages(audit, "LLM_PROVIDER_CALL_FAILED")
    failed_attempts = _all_stages(audit, "LLM_PROVIDER_ATTEMPT_FAILED")
    provider_attempt_count = len(successful_calls) + len(failed_calls) + len(failed_attempts)
    input_tokens, input_complete = _sum_known(successful_calls, "input_tokens")
    output_tokens, output_complete = _sum_known(successful_calls, "output_tokens")
    total_tokens, total_complete = _sum_known(successful_calls, "total_tokens")
    reasoning_tokens, reasoning_complete = _sum_known(successful_calls, "reasoning_tokens")
    cached_tokens, cached_complete = _sum_known(successful_calls, "cached_tokens")
    cache_write_tokens, cache_write_complete = _sum_known(successful_calls, "cache_write_tokens")
    provider_latency_ms, latency_complete = _sum_known(successful_calls + failed_calls + failed_attempts, "latency_ms")
    tool_records = _all_stages(audit, "TOOL_CALL")
    tool_latency_ms, tool_latency_complete = _sum_known(tool_records, "latency_ms")
    validation_records = _all_stages(audit, "LLM_CONTRACT")
    validation_latency_ms, validation_complete = _sum_known(validation_records, "validation_latency_ms")

    cost_values = [record.get("cost_usd") for record in successful_calls]
    cost_complete = (
        bool(successful_calls)
        and not failed_calls
        and not failed_attempts
        and all(isinstance(value, (int, float)) for value in cost_values)
    )
    cost_usd = sum(float(value) for value in cost_values) if cost_values and all(isinstance(value, (int, float)) for value in cost_values) else None

    prompt_breakdown: dict[str, int] = {}
    for record in successful_calls:
        profile = record.get("prompt_profile") or {}
        estimated = profile.get("component_tokens_estimated") if isinstance(profile, dict) else None
        if isinstance(estimated, dict):
            for name, value in estimated.items():
                if isinstance(value, int):
                    prompt_breakdown[name] = prompt_breakdown.get(name, 0) + value

    return {
        "case_latency_ms": round(case_latency_ms, 2),
        "decision_stage_count": int(any(item.get("stage") == "INITIAL_DECISION" for item in audit)) + int(any(item.get("stage") == "FOLLOWUP_DECISION" for item in audit)),
        "provider_call_count": provider_attempt_count,
        "provider_successful_call_count": len(successful_calls),
        "repair_call_count": sum(1 for item in successful_calls + failed_calls if item.get("strategy") == "REPAIR"),
        "format_fallback_count": sum(1 for item in successful_calls if item.get("strategy") == "FORMAT_FALLBACK"),
        "tool_call_count": len(tool_records),
        "input_tokens": input_tokens,
        "input_tokens_complete": input_complete,
        "output_tokens": output_tokens,
        "output_tokens_complete": output_complete,
        "reasoning_tokens": reasoning_tokens,
        "reasoning_tokens_complete": reasoning_complete,
        "cached_tokens": cached_tokens,
        "cached_tokens_complete": cached_complete,
        "cache_write_tokens": cache_write_tokens,
        "cache_write_tokens_complete": cache_write_complete,
        "total_tokens": total_tokens,
        "total_tokens_complete": total_complete,
        "provider_latency_ms": provider_latency_ms,
        "provider_latency_complete": latency_complete,
        "tool_latency_ms": tool_latency_ms,
        "tool_latency_complete": tool_latency_complete,
        "validation_latency_ms": validation_latency_ms,
        "validation_latency_complete": validation_complete,
        "provider_cost_usd": cost_usd,
        "provider_cost_complete": cost_complete,
        "prompt_component_tokens_estimated": prompt_breakdown,
        "followup_context_replayed": any(item.get("context_replayed") for item in successful_calls if item.get("llm_stage") == "FOLLOWUP_AFTER_TOOLS"),
        "followup_previous_decision_included": any(item.get("previous_decision_included") for item in successful_calls if item.get("llm_stage") == "FOLLOWUP_AFTER_TOOLS"),
        "followup_tool_results_included": any(item.get("tool_results_included") for item in successful_calls if item.get("llm_stage") == "FOLLOWUP_AFTER_TOOLS"),
        "note": "provider token/cost는 실제 usage, prompt component token은 실제 input token을 문자 비율로 나눈 추정치다.",
    }


def _percentile(values: list[float], percentile: float) -> float | None:
    if not values:
        return None
    if len(values) == 1:
        return round(values[0], 2)
    ordered = sorted(values)
    index = (len(ordered) - 1) * percentile
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = index - lower
    return round(ordered[lower] + (ordered[upper] - ordered[lower]) * fraction, 2)


def _write_safe_case_csv(path: Path, summary: dict[str, Any], results: list[dict[str, Any]]) -> None:
    """공유 가능한 사례별 수치만 보존한다. 원문·응답·힌트·검토 근거는 제외한다."""
    fields = (
        "selection_run_id", "evaluation_run_id", "dataset_sha256", "quality_contract_sha256",
        "model", "case_id", "langfuse_trace_id", "execution_status", "quality_status",
        "structured_output_status", "instruction_adherence", "context_understanding",
        "domain_judgment", "tool_judgment", "observation_interpretation", "decision_consistency",
        "hard_fail_auto", "provider_call_count", "tool_call_count", "total_tokens",
        "provider_cost_usd", "case_latency_ms",
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for result in results:
            scorecard = result.get("project_model_capability_scorecard") or {}
            metrics = result.get("metrics") or {}
            writer.writerow({
                "selection_run_id": summary.get("selection_run_id"),
                "evaluation_run_id": summary.get("evaluation_run_id"),
                "dataset_sha256": summary.get("dataset_sha256"),
                "quality_contract_sha256": summary.get("quality_contract_sha256"),
                "model": summary.get("model"),
                "case_id": result.get("id"),
                "langfuse_trace_id": result.get("langfuse_trace_id"),
                "execution_status": result.get("execution_status"),
                "quality_status": (result.get("quality_contract_gate") or {}).get("status"),
                "structured_output_status": (scorecard.get("structured_output_stability") or {}).get("status"),
                **{axis: (scorecard.get(axis) or {}).get("status") for axis in (
                    "instruction_adherence", "context_understanding", "domain_judgment",
                    "tool_judgment", "observation_interpretation", "decision_consistency",
                )},
                "hard_fail_auto": (result.get("quality_contract_gate") or {}).get("hard_fail_auto"),
                "provider_call_count": metrics.get("provider_call_count"),
                "tool_call_count": metrics.get("tool_call_count"),
                "total_tokens": metrics.get("total_tokens"),
                "provider_cost_usd": metrics.get("provider_cost_usd"),
                "case_latency_ms": metrics.get("case_latency_ms"),
            })


def _evaluate_case(
    row: dict[str, Any],
    response: AgentResponse,
    audit: list[dict[str, Any]],
    master_requests: list[dict[str, Any]],
    quality_case: dict[str, Any] | None = None,
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
            "handoff_texts": [f"{item.get('reason', '')}: {item.get('summary', '')}" for item in handoff_rows[-3:]],
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
    execution = _last_stage(audit, "EXECUTION") or {}
    final = _last_stage(audit, "FINAL_RESPONSE") or response.model_dump(mode="json")

    # 세 축은 서로 상쇄하지 않는다. Domain은 사람 의미 검토가 끝나기 전 점수화하지 않는다.
    domain_axis = {
        "status": "REVIEW_REQUIRED" if row.get("human_validated") else "NOT_SCORED_NO_HUMAN_GROUND_TRUTH",
        "initial_decision": initial or None,
        "followup_decision": followup or None,
        "human_expected_description": row.get("expected"),
        "note": "Pydantic/실행 성공과 별개로 한국어 의미 판단·도구 결과 해석·행동 적절성을 검토한다.",
    }

    execution_failures = [
        name for name, check in automatic_checks.items()
        if name in {"processing_vs_final_guidance_structure", "final_actions", "final_status"}
        and check.get("status") == "FAIL"
    ]
    execution_axis = {
        "status": "FAIL" if execution_failures else ("PASS" if automatic_checks["processing_vs_final_guidance_structure"]["status"] == "PASS" else "REVIEW_REQUIRED"),
        "failed_checks": execution_failures,
        "execution_observation": execution or None,
        "final_response_status": response.status.value,
    }

    contract_failed = any(report.get("raw_contract_valid") is False for report in contract_reports)
    safety_axis = {
        "status": "FAIL" if contract_failed else ("PASS" if contract_reports else "NOT_APPLICABLE_BASELINE_OR_NO_LLM_CONTRACT"),
        "raw_contract_reports": contract_reports,
        "note": "계약/권한/보호 경계 축이며 Domain 판단의 정답 여부와 별도다.",
    }

    trajectory = {
        "INITIAL": initial or None,
        "TOOL": lookup or None,
        "FOLLOWUP": followup or None,
        "EXECUTION": execution or None,
        "RESPONSE": final,
    }
    quality_gate = _quality_contract_checks(quality_case or {}, response, audit) if quality_case is not None else {
        "status": "NOT_CONFIGURED",
        "hard_fail_auto": False,
    }

    return {
        "automatic_checks": automatic_checks,
        "human_review": human_review,
        "contract_reports": contract_reports,
        "evaluation_axes": {
            "domain_decision_quality": domain_axis,
            "execution_quality": execution_axis,
            "safety_contract_quality": safety_axis,
        },
        "decision_trajectory": trajectory,
        "quality_contract_gate": quality_gate,
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
    max_cost_usd: float | None = None,
    phase: str = "unspecified",
    model: str | None = None,
    quality_contract_path: Path = DEFAULT_QUALITY_CONTRACT,
    selection_run_id: str | None = None,
    csv_output: Path | None = None,
) -> dict[str, Any]:
    rows = load_rows(dataset)
    dataset_sha256 = _sha256(dataset)
    canonical_dataset = (ROOT / "evals/dataset.jsonl").resolve()
    quality_contract: dict[str, Any] = {"cases": {}}
    quality_contract_enabled = dataset.resolve() == canonical_dataset
    if quality_contract_enabled:
        quality_contract = _load_quality_contract(quality_contract_path)
        if quality_contract.get("dataset_sha256") != dataset_sha256:
            summary = {
                "status": "NOT_RUN_QUALITY_CONTRACT_DATASET_HASH_MISMATCH",
                "dataset": str(dataset),
                "dataset_sha256": dataset_sha256,
                "quality_contract": str(quality_contract_path),
                "quality_contract_dataset_sha256": quality_contract.get("dataset_sha256"),
            }
            output.parent.mkdir(parents=True, exist_ok=True)
            output.write_text(json.dumps({"summary": summary, "results": []}, ensure_ascii=False, indent=2), encoding="utf-8")
            return summary
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

    phase_budget_ceiling = (
        MODEL_SELECTION_TOTAL_BUDGET_USD if phase == "model_selection" else PROJECT_TEST_BUDGET_USD
    )
    if provider == "openrouter" and (
        max_cost_usd is None or max_cost_usd <= 0 or max_cost_usd > phase_budget_ceiling
    ):
        summary = {
            "status": "NOT_RUN_INVALID_OR_MISSING_COST_CAP",
            "provider": provider,
            "phase": phase,
            "max_cost_usd": max_cost_usd,
            "phase_budget_ceiling_usd": phase_budget_ceiling,
            "project_budget_reference_usd": PROJECT_TEST_BUDGET_USD,
            "note": (
                "model_selection 단계는 4모델 전체 $5 상한 안에서만 실행한다. "
                "그 외 평가 단계의 프로젝트 참고 상한은 $30이다."
            ),
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"summary": summary, "results": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary

    selected_model = (model or os.getenv("OPENROUTER_MODEL", "")).strip() if provider == "openrouter" else None
    if provider == "openrouter" and not os.getenv("OPENROUTER_API_KEY", "").strip():
        summary = {
            "status": "NOT_RUN_API_KEY_MISSING",
            "provider": provider,
            "phase": phase,
            "rows_planned": len(rows),
            "note": "키 값을 대화/로그에 넣지 말고 로컬 프로세스 환경변수로만 제공한다.",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"summary": summary, "results": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary
    if provider == "openrouter" and not selected_model:
        summary = {
            "status": "NOT_RUN_MODEL_ID_REQUIRED",
            "provider": provider,
            "phase": phase,
            "note": "OPENROUTER_MODEL 또는 --model에 검증할 정확한 model ID를 지정한다. free/임의 fallback 없음.",
        }
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps({"summary": summary, "results": []}, ensure_ascii=False, indent=2), encoding="utf-8")
        return summary


    evaluation_run_id = uuid4().hex
    evaluation_started_at = datetime.now(timezone.utc).isoformat()
    quality_contract_sha256 = _sha256(quality_contract_path) if quality_contract_enabled else None
    results: list[dict[str, Any]] = []
    observability_complete = True if allow_observability_export else None
    failed = 0
    completed = 0
    auto_scored = 0
    auto_passed = 0
    raw_contract_reports = 0
    raw_contract_valid = 0
    normalization_changed = 0
    reported_cost_usd = 0.0
    cost_complete = True
    budget_stop_reason: str | None = None
    quality_pass_cases = 0
    quality_fail_cases = 0
    quality_review_required_cases = 0
    hard_fail_auto_cases = 0
    case_latency_values: list[float] = []
    provider_call_total = 0
    repair_call_total = 0
    format_fallback_total = 0
    tool_call_total = 0
    token_totals = {
        "input_tokens": 0,
        "output_tokens": 0,
        "reasoning_tokens": 0,
        "cached_tokens": 0,
        "cache_write_tokens": 0,
        "total_tokens": 0,
    }
    token_completeness = {key: True for key in token_totals}
    prompt_component_totals: dict[str, int] = {}

    with _observability_export(allow_observability_export):
        for index, row in enumerate(rows, 1):
            if provider == "openrouter" and reported_cost_usd >= float(max_cost_usd):
                budget_stop_reason = "PHASE_COST_CAP_REACHED"
                break
            case_id = _safe_case_id(row, index)
            audit: list[dict[str, Any]] = []
            quality_case = (quality_contract.get("cases") or {}).get(str(row.get("id", case_id)))
            case_started = time.perf_counter()
            try:
                with isolated_agent_runtime() as client:
                    request = _seed_case(client, row, index, evaluation_run_id)
                    response = agent_orchestrator.handle_agent_request(
                        request,
                        llm_provider=provider,
                        evaluation_audit=audit,
                    )
                    master_requests = client.master_request_status(request.session_id, request.team_id, limit=20)
                    case_eval = _evaluate_case(row, response, audit, master_requests, quality_case)

                    for check in case_eval["automatic_checks"].values():
                        if check.get("status") in {"PASS", "FAIL"}:
                            auto_scored += 1
                            auto_passed += check["status"] == "PASS"
                    for contract in case_eval["contract_reports"]:
                        raw_contract_reports += 1
                        raw_contract_valid += bool(contract.get("raw_contract_valid"))
                        normalization_changed += bool(contract.get("normalization_changed_fields"))

                    case_latency_ms = round((time.perf_counter() - case_started) * 1000, 2)
                    metrics = _case_metrics(audit, case_latency_ms)
                    case_latency_values.append(case_latency_ms)
                    provider_call_total += int(metrics["provider_call_count"])
                    repair_call_total += int(metrics["repair_call_count"])
                    format_fallback_total += int(metrics["format_fallback_count"])
                    tool_call_total += int(metrics["tool_call_count"])
                    for token_key in token_totals:
                        value = metrics.get(token_key)
                        if isinstance(value, (int, float)):
                            token_totals[token_key] += int(value)
                        if metrics.get(f"{token_key}_complete") is False:
                            token_completeness[token_key] = False
                    for component, value in (metrics.get("prompt_component_tokens_estimated") or {}).items():
                        if isinstance(value, int):
                            prompt_component_totals[component] = prompt_component_totals.get(component, 0) + value
                    quality_status = case_eval["quality_contract_gate"]["status"]
                    quality_pass_cases += quality_status == "PASS"
                    quality_fail_cases += quality_status == "FAIL"
                    quality_review_required_cases += quality_status == "REVIEW_REQUIRED"
                    hard_fail_auto_cases += bool(case_eval["quality_contract_gate"].get("hard_fail_auto"))

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
                            "metrics": metrics,
                            "project_model_capability_scorecard": build_scorecard(
                                provider=provider, execution_status="COMPLETED", audit=audit,
                                case_evaluation=case_eval, metrics=metrics,
                            ),
                            **case_eval,
                        }
                    )
            except Exception as exc:
                failed += 1
                case_latency_ms = round((time.perf_counter() - case_started) * 1000, 2)
                metrics = _case_metrics(audit, case_latency_ms)
                case_latency_values.append(case_latency_ms)
                provider_call_total += int(metrics["provider_call_count"])
                repair_call_total += int(metrics["repair_call_count"])
                format_fallback_total += int(metrics["format_fallback_count"])
                tool_call_total += int(metrics["tool_call_count"])
                for token_key in token_totals:
                    value = metrics.get(token_key)
                    if isinstance(value, (int, float)):
                        token_totals[token_key] += int(value)
                    if metrics.get(f"{token_key}_complete") is False:
                        token_completeness[token_key] = False
                quality_fail_cases += 1
                results.append(
                    {
                        "id": row.get("id", case_id),
                        "execution_status": "FAILED",
                        "provider": provider,
                        "error_type": type(exc).__name__,
                        "trace": audit,
                        "metrics": metrics,
                        "automatic_checks": {},
                        "quality_contract_gate": {"status": "FAIL", "reason": "EXECUTION_FAILED"},
                        "human_review": {"failure_analysis": {"status": "REVIEW_REQUIRED"}},
                        "project_model_capability_scorecard": build_scorecard(
                            provider=provider, execution_status="FAILED", audit=audit,
                            case_evaluation={"quality_contract_gate": {"status": "FAIL"}}, metrics=metrics,
                        ),
                    }
                )

            result = results[-1]
            trace_seed = f"eval_{evaluation_run_id}_{case_id}"
            result.update({
                "evaluation_run_id": evaluation_run_id,
                "selection_run_id": selection_run_id,
                "trace_seed": trace_seed,
                "langfuse_trace_id": trace_id_for_seed(trace_seed),
                "dataset_sha256": dataset_sha256,
                "quality_contract_sha256": quality_contract_sha256,
                "model": selected_model,
            })
            if allow_observability_export:
                safe = {
                    "trace_id": trace_seed,
                    "evaluation_name": dataset.name,
                    "evaluation_run_id": evaluation_run_id,
                    "selection_run_id": selection_run_id,
                    "evaluation_case_id": row.get("id", case_id),
                    "dataset_sha256": dataset_sha256,
                    "quality_contract_sha256": quality_contract_sha256,
                    "quality_status": result["quality_contract_gate"]["status"],
                    "status": result["execution_status"],
                    "llm_provider": provider,
                    "llm_model": selected_model,
                    "latency_ms": result["metrics"].get("case_latency_ms"),
                    "total_tokens": result["metrics"].get("total_tokens"),
                    "cost_usd": result["metrics"].get("provider_cost_usd"),
                }
                exported = record_event("evaluation_case", safe)
                scorecard = result["project_model_capability_scorecard"]
                automatic_scores = {
                    "structured_output_stability": scorecard["structured_output_stability"]["status"],
                    "core30_auto_contract": result["quality_contract_gate"]["status"],
                    "hard_fail_auto_guard": "FAIL" if result["quality_contract_gate"].get("hard_fail_auto") else "PASS",
                }
                for score_name, status in automatic_scores.items():
                    if status not in {"PASS", "FAIL"}:
                        continue
                    exported = record_evaluation_score(
                        trace_seed=trace_seed, name=score_name, value=1.0 if status == "PASS" else 0.0,
                        evaluation_started_at=evaluation_started_at, evaluation_run_id=evaluation_run_id,
                        case_id=int(row["id"]) if str(row.get("id", "")).isdigit() else index,
                        dataset_sha256=dataset_sha256,
                        model=selected_model or provider,
                    ) and exported
                if not exported:
                    observability_complete = False
                    budget_stop_reason = "LANGFUSE_EXPORT_FAILED_STOP_AFTER_CASE"

            if provider == "openrouter":
                latest_metrics = results[-1].get("metrics", {}) if results else {}
                case_cost = latest_metrics.get("provider_cost_usd")
                if latest_metrics.get("provider_call_count", 0) and latest_metrics.get("provider_cost_complete") is not True:
                    cost_complete = False
                    if observability_complete is not False:
                        budget_stop_reason = "PROVIDER_COST_UNKNOWN_STOP_AFTER_CASE"
                elif isinstance(case_cost, (int, float)):
                    reported_cost_usd += float(case_cost)
                    results[-1]["provider_cost_usd_reported"] = float(case_cost)
                    results[-1]["provider_call_count"] = int(latest_metrics.get("provider_call_count", 0))
                if budget_stop_reason:
                    break
                if reported_cost_usd >= float(max_cost_usd):
                    budget_stop_reason = "PHASE_COST_CAP_REACHED"
                    break
            if observability_complete is False:
                break

    summary = {
        "status": (
            "STOPPED_LANGFUSE_EXPORT_FAILED" if budget_stop_reason == "LANGFUSE_EXPORT_FAILED_STOP_AFTER_CASE"
            else "STOPPED_COST_UNKNOWN" if budget_stop_reason == "PROVIDER_COST_UNKNOWN_STOP_AFTER_CASE"
            else "STOPPED_PHASE_COST_CAP" if budget_stop_reason
            else "COMPLETED_WITH_FAILURES" if failed
            else "COMPLETED"
        ),
        "dataset": str(dataset),
        "dataset_sha256": dataset_sha256,
        "evaluation_run_id": evaluation_run_id,
        "selection_run_id": selection_run_id,
        "evaluation_started_at": evaluation_started_at,
        "observability_complete": observability_complete,
        "quality_contract": str(quality_contract_path) if quality_contract_enabled else None,
        "quality_contract_sha256": _sha256(quality_contract_path) if quality_contract_enabled else None,
        "project_model_capability_scorecard_summary": scorecard_counts(results),
        "evaluation_code_fingerprint": _evaluation_code_fingerprint(),
        "provider": provider,
        "model": selected_model,
        "phase": phase,
        "max_cost_usd": max_cost_usd,
        "provider_cost_usd_reported": round(reported_cost_usd, 8),
        "provider_cost_complete": cost_complete,
        "budget_stop_reason": budget_stop_reason,
        "rows_planned": len(rows),
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
        "quality_contract_pass_cases": quality_pass_cases,
        "quality_contract_fail_cases": quality_fail_cases,
        "quality_contract_review_required_cases": quality_review_required_cases,
        "hard_fail_auto_cases": hard_fail_auto_cases,
        "model_selection_quality_gate": (
            "INCOMPLETE" if completed + failed < len(rows)
            else "FAIL" if quality_fail_cases or hard_fail_auto_cases or failed
            else "REVIEW_REQUIRED" if quality_review_required_cases
            else "PASS"
        ),
        "provider_call_count": provider_call_total,
        "provider_calls_per_completed_case": (provider_call_total / completed if completed else None),
        "repair_call_count": repair_call_total,
        "format_fallback_count": format_fallback_total,
        "tool_call_count": tool_call_total,
        "token_totals": token_totals,
        "token_completeness": token_completeness,
        "prompt_component_tokens_estimated": prompt_component_totals,
        "latency_p50_ms": _percentile(case_latency_values, 0.50),
        "latency_p95_ms": _percentile(case_latency_values, 0.95),
        "domain_quality_rate": (quality_pass_cases / len(rows) if len(rows) and not quality_review_required_cases and not quality_fail_cases and completed == len(rows) else None),
        "note": (
            "평가 세션/MCP/부작용은 MemoryRuntime에 격리. 합성/미검증 row는 도메인 품질 점수로 집계하지 않으며 "
            "Domain / Execution / Safety-Contract 세 축은 서로 상쇄하지 않는다. 질문 적절성·직원 전달 사실성·"
            "Skill 규칙의 올바른 적용·최종 안내 의미 일치는 사람 검토 대상."
        ),
    }
    if allow_observability_export:
        exported = record_event(
            "evaluation_run",
            {
                "evaluation_name": dataset.name,
                "evaluation_score": summary["domain_quality_rate"],
                "evaluation_run_id": evaluation_run_id,
                "selection_run_id": selection_run_id,
                "dataset_sha256": dataset_sha256,
                "quality_contract_sha256": quality_contract_sha256,
                "quality_status": summary["model_selection_quality_gate"],
                "status": summary["status"],
                "llm_provider": provider,
                "llm_model": selected_model,
                "total_tokens": token_totals.get("total_tokens"),
                "cost_usd": summary["provider_cost_usd_reported"],
            },
        )
        if not exported:
            summary["observability_complete"] = False
            summary["status"] = "STOPPED_LANGFUSE_EXPORT_FAILED"
    if csv_output is not None:
        try:
            _write_safe_case_csv(csv_output, summary, results)
            summary["csv_output"] = str(csv_output)
            summary["csv_export_complete"] = True
        except (OSError, ValueError):
            summary["csv_export_complete"] = False
            summary["status"] = "STOPPED_CSV_EXPORT_FAILED"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"summary": summary, "results": results}, ensure_ascii=False, indent=2), encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/dataset.jsonl")
    parser.add_argument("--provider", choices=["baseline", "openrouter"], required=True)
    parser.add_argument("--output", default="evals/results/latest_service_flow.json")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--model", default=None, help="Exact OpenRouter model ID, after ZDR catalog preflight")
    parser.add_argument("--max-cost-usd", type=float, default=None, help="OpenRouter cost stop threshold. model_selection phase <= $5; other phases <= $30 reference ceiling")
    parser.add_argument("--phase", default="unspecified", help="model_capability|pipeline|integration|demo_rehearsal")
    parser.add_argument("--quality-contract", default="evals/core30_quality_contract.json")
    parser.add_argument("--csv-output", default=None, help="Optional safe metrics CSV; excludes raw customer/model text")
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
    previous_model = os.environ.get("OPENROUTER_MODEL")
    if args.provider == "openrouter" and args.model:
        os.environ["OPENROUTER_MODEL"] = args.model
    try:
        summary = run(
            Path(args.dataset),
            args.provider,
            output,
            limit=args.limit,
            allow_external_llm=args.allow_external_llm,
            allow_observability_export=args.allow_observability_export,
            max_cost_usd=args.max_cost_usd,
            phase=args.phase,
            model=args.model,
            quality_contract_path=Path(args.quality_contract),
            csv_output=Path(args.csv_output) if args.csv_output else None,
        )
    finally:
        if args.provider == "openrouter":
            if previous_model is None:
                os.environ.pop("OPENROUTER_MODEL", None)
            else:
                os.environ["OPENROUTER_MODEL"] = previous_model
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
