from datetime import datetime, timezone
import time
from typing import Any

from backend.schemas import (
    AgentActionType,
    AgentRequest,
    AgentResponse,
    AgentStatus,
    HintEvent,
    IntentResult,
    LookupToolType,
    SupportNeed,
)
from backend.services.answer_vault import create_answer_offer
from backend.services.context_builder import build_agent_context
from backend.services.domain_skill import filter_reported_skill_rule_ids
from backend.services.hint_policy import select_approved_hint_strength
from backend.services.langfuse_service import record_event
from backend.services.llm import analyze_after_tools, analyze_user_request
from backend.services.mcp_client import MCPClient
from backend.services.slack_notification import MockSlackNotificationAdapter


mcp = MCPClient()
slack_notification_adapter = MockSlackNotificationAdapter()


def _append_audit(audit: list[dict[str, Any]] | None, item: dict[str, Any]) -> None:
    if audit is not None:
        audit.append(item)


def _decision_audit(stage: str, intent: IntentResult) -> dict[str, Any]:
    """평가용으로 원문 없이 판단 구조만 남긴다."""
    return {
        "stage": stage,
        "intent": intent.intent.value,
        "intents": [item.value for item in intent.intents],
        "actions": [item.value for item in intent.actions],
        "lookup_tools": [item.value for item in intent.lookup_tools],
        "needs_clarification": intent.needs_clarification,
        "clarifying_question": intent.clarifying_question,
        "support_need": intent.support_need.value,
        "staff_facts": list(intent.staff_facts),
        "staff_attempts": list(intent.staff_attempts),
        "staff_unknowns": list(intent.staff_unknowns),
        "reported_applied_skill_rules": list(intent.applied_skill_rules),
        "provider": intent.provider,
        "model": intent.model,
        "prompt_version": intent.prompt_version,
        "skill_version": intent.skill_version,
    }


def _record_response_event(event_name: str, request: AgentRequest, response: AgentResponse) -> None:
    # 외부 관측 경계에는 고객 원문/힌트 원문/직원 summary를 보내지 않는다.
    record_event(
        event_name,
        {
            "trace_id": request.request_id,
            "request_id": request.request_id,
            "session_id": response.session_id,
            "status": response.status.value,
            "intent": response.intent.value if response.intent else None,
            "selected_tools": list(response.selected_tools),
            "completed_actions": [item.value for item in response.completed_actions],
            "pending_actions": [item.value for item in response.pending_actions],
            "llm_provider": response.llm_provider,
            "llm_model": response.llm_model,
            "prompt_version": response.prompt_version,
            "skill_version": response.skill_version,
            "llm_call_count": response.llm_call_count,
            "decision_source": response.decision_source,
        },
    )


def _get_hint_with_retry(
    session_id: str,
    team_id: str,
    puzzle_id: str,
    strength: str,
    *,
    request_id: str | None = None,
) -> str:
    """승인 힌트 조회의 일시적인 연결 오류만 1회 재시도한다."""
    for attempt in range(2):
        started = time.perf_counter()
        try:
            value = mcp.get_hint(session_id, team_id, puzzle_id, strength)
            record_event(
                "tool_call",
                {
                    "trace_id": request_id,
                    "request_id": request_id,
                    "session_id": session_id,
                    "tool_name": "get_approved_hint",
                    "tool_status": "SUCCESS",
                    "retry_count": attempt,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            return value
        except (TimeoutError, ConnectionError) as exc:
            record_event(
                "tool_call",
                {
                    "trace_id": request_id,
                    "request_id": request_id,
                    "session_id": session_id,
                    "tool_name": "get_approved_hint",
                    "tool_status": "RETRY" if attempt == 0 else "FAILED",
                    "retry_count": attempt,
                    "error_type": type(exc).__name__,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            if attempt == 1:
                raise
    raise RuntimeError("APPROVED_HINT_LOOKUP_FAILED")


def _assistant_turn_text(response: AgentResponse) -> str:
    if response.customer_message:
        return response.customer_message
    if response.hint_text:
        return "승인된 힌트를 제공함"
    return response.status.value


def _staff_handoff_detail(intent: IntentResult) -> str:
    """직원 전달 시 사실/시도/미확인을 섞지 않는다."""
    parts: list[str] = []
    if intent.staff_facts:
        parts.append("고객 사실: " + "; ".join(intent.staff_facts))
    if intent.staff_attempts:
        parts.append("고객 시도: " + "; ".join(intent.staff_attempts))
    if intent.staff_unknowns:
        parts.append("미확인: " + "; ".join(intent.staff_unknowns))
    return (" | ".join(parts) or intent.reason or "CUSTOMER_OPERATION_REQUEST")[:1200]


def _execute_lookup_tools(
    intent: IntentResult,
    *,
    session_id: str,
    team_id: str,
    puzzle_id: str | None,
    request_id: str | None = None,
    evaluation_audit: list[dict[str, Any]] | None = None,
) -> tuple[dict[str, object], list[str]]:
    """LLM이 선택한 읽기 전용 조회만 코드 경계 안에서 실행한다."""
    results: dict[str, object] = {}
    executed: list[str] = []

    for lookup in intent.lookup_tools:
        started = time.perf_counter()
        try:
            if lookup == LookupToolType.GET_HINT_HISTORY:
                if puzzle_id is None:
                    results[lookup.value] = {"status": "NOT_AVAILABLE", "reason": "PUZZLE_ID_REQUIRED"}
                else:
                    history = mcp.get_history(session_id, team_id, puzzle_id)
                    results[lookup.value] = [
                        item.model_dump(mode="json") if hasattr(item, "model_dump") else dict(item)
                        for item in history[-5:]
                    ]
                executed.append(lookup.value)
            elif lookup == LookupToolType.GET_MASTER_REQUEST_STATUS:
                results[lookup.value] = mcp.master_request_status(session_id, team_id, limit=5)
                executed.append(lookup.value)
            else:
                continue
            tool_latency_ms = round((time.perf_counter() - started) * 1000, 2)
            record_event(
                "tool_call",
                {
                    "trace_id": request_id,
                    "request_id": request_id,
                    "session_id": session_id,
                    "tool_name": lookup.value,
                    "tool_status": "SUCCESS",
                    "latency_ms": tool_latency_ms,
                },
            )
            _append_audit(
                evaluation_audit,
                {
                    "stage": "TOOL_CALL",
                    "tool_name": lookup.value,
                    "tool_status": "SUCCESS",
                    "latency_ms": tool_latency_ms,
                    "result_size_chars": len(str(results.get(lookup.value))),
                    "llm_tokens_used_by_tool_execution": 0,
                },
            )
        except Exception as exc:
            tool_latency_ms = round((time.perf_counter() - started) * 1000, 2)
            record_event(
                "tool_call",
                {
                    "trace_id": request_id,
                    "request_id": request_id,
                    "session_id": session_id,
                    "tool_name": lookup.value,
                    "tool_status": "FAILED",
                    "error_type": type(exc).__name__,
                    "latency_ms": tool_latency_ms,
                },
            )
            _append_audit(
                evaluation_audit,
                {
                    "stage": "TOOL_CALL",
                    "tool_name": lookup.value,
                    "tool_status": "FAILED",
                    "latency_ms": tool_latency_ms,
                    "error_type": type(exc).__name__,
                    "llm_tokens_used_by_tool_execution": 0,
                },
            )
            raise

    return results, executed


def _clarification_response(
    *,
    request: AgentRequest,
    session_id: str,
    team_id: str,
    puzzle_id: str | None,
    intent: IntentResult,
    selected_tools: list[str],
    llm_call_count: int,
    evaluation_audit: list[dict[str, Any]] | None = None,
) -> AgentResponse:
    question = intent.clarifying_question or "확인할 내용을 한 가지 더 알려주세요."
    response = AgentResponse(
        status=AgentStatus.NEED_MORE_INFO,
        session_id=session_id,
        team_id=team_id,
        puzzle_id=puzzle_id,
        intent=intent.intent,
        emotion=intent.emotion,
        decision_source="LLM_CLARIFICATION+CODE_GUARD",
        reason_codes=[intent.reason] + [f"LLM_REPORTED_SKILL_RULE:{x}" for x in filter_reported_skill_rule_ids(intent.applied_skill_rules)],
        selected_tools=selected_tools,
        llm_provider=intent.provider,
        llm_model=intent.model,
        prompt_version=intent.prompt_version,
        skill_version=intent.skill_version,
        llm_call_count=llm_call_count,
        next_action="ASK_CLARIFICATION",
        customer_message=question,
        pending_actions=[AgentActionType.ASK_CLARIFICATION],
        context_notes=intent.context_notes,
    )
    mcp.record_conversation_turn(session_id, "assistant", question, request.request_id)
    _append_audit(evaluation_audit, {"stage": "FINAL_RESPONSE", **response.model_dump(mode="json")})
    _record_response_event("need_more_info", request, response)
    return response


def handle_agent_request(
    request: AgentRequest,
    *,
    llm_provider: str | None = None,
    evaluation_audit: list[dict[str, Any]] | None = None,
) -> AgentResponse:
    # 1) 세션/팀/현재 퍼즐을 먼저 검증하고 최소 맥락 + 버전이 있는 Domain Skill만 LLM에 제공한다.
    session, context = build_agent_context(
        mcp,
        session_id=request.session_id,
        team_id=request.team_id,
        requested_puzzle_id=request.puzzle_id,
    )
    effective_puzzle_id = context.requested_puzzle_id

    if session.is_closed or context.remaining_time_minutes <= 0:
        response = AgentResponse(
            status=AgentStatus.CLOSED,
            session_id=session.session_id,
            team_id=session.team_id,
            puzzle_id=effective_puzzle_id,
            decision_source="SESSION_POLICY",
            next_action="SESSION_CLOSED",
        )
        _append_audit(evaluation_audit, {"stage": "FINAL_RESPONSE", **response.model_dump(mode="json")})
        _record_response_event("agent_request_closed", request, response)
        return response

    # build_agent_context가 고객 puzzle_id 불일치를 LLM/MCP 조회 전에 차단한다.
    # 방어적으로 이 경로에 도달해도 운영 큐를 만들거나 다른 퍼즐을 조회하지 않는다.
    if effective_puzzle_id and session.current_puzzle_id and effective_puzzle_id != session.current_puzzle_id:
        response = AgentResponse(
            status=AgentStatus.NEED_MORE_INFO,
            session_id=session.session_id,
            team_id=session.team_id,
            puzzle_id=session.current_puzzle_id,
            decision_source="PUZZLE_ID_GUARD",
            reason_codes=["PUZZLE_ID_MISMATCH"],
            next_action="REFRESH_CURRENT_PUZZLE",
            customer_message="현재 진행 중인 문제 정보와 요청이 일치하지 않습니다. 화면을 새로고침한 뒤 다시 요청해 주세요.",
        )
        _append_audit(evaluation_audit, {"stage": "FINAL_RESPONSE", **response.model_dump(mode="json")})
        _record_response_event("puzzle_id_mismatch", request, response)
        return response

    # 2) LLM 1차 판단: 의미/복합성/필요 조회/질문/행동 계획을 구조화한다.
    try:
        intent = analyze_user_request(
            request.message,
            context,
            provider=llm_provider,
            request_id=request.request_id,
            audit=evaluation_audit,
        )
    except Exception as exc:
        response = AgentResponse(
            status=AgentStatus.ERROR,
            session_id=session.session_id,
            team_id=session.team_id,
            puzzle_id=effective_puzzle_id,
            decision_source="LLM_ERROR",
            reason_codes=[type(exc).__name__],
            next_action="RETRY_OR_OPERATOR_CHECK",
            customer_message="요청을 해석하는 과정에서 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
        )
        _append_audit(
            evaluation_audit,
            {"stage": "ERROR", "where": "INITIAL_LLM", "error_type": type(exc).__name__},
        )
        _append_audit(evaluation_audit, {"stage": "FINAL_RESPONSE", **response.model_dump(mode="json")})
        _record_response_event("llm_decision_failed", request, response)
        return response

    _append_audit(evaluation_audit, _decision_audit("INITIAL_DECISION", intent))
    llm_call_count = 1
    selected_tools: list[str] = []

    # 3) 과거 상태가 필요한 경우에만 LLM이 고른 읽기 전용 조회를 실행하고 2차 판단한다.
    if intent.lookup_tools:
        try:
            tool_results, lookup_tools = _execute_lookup_tools(
                intent,
                session_id=session.session_id,
                team_id=session.team_id,
                puzzle_id=effective_puzzle_id,
                request_id=request.request_id,
                evaluation_audit=evaluation_audit,
            )
        except Exception as exc:
            # 수정 사유: 선택 조회 실패를 LLM 추측이나 부작용 실행으로 이어가지 않는다.
            # 사용자는 안전한 실패 상태를 받고, 운영자는 request_id로 실패 단계를 추적한다.
            response = AgentResponse(
                status=AgentStatus.ERROR,
                session_id=session.session_id,
                team_id=session.team_id,
                puzzle_id=effective_puzzle_id,
                intent=intent.intent,
                emotion=intent.emotion,
                decision_source="READ_ONLY_TOOL_ERROR",
                reason_codes=["LOOKUP_TOOL_FAILED", type(exc).__name__],
                selected_tools=[item.value for item in intent.lookup_tools],
                llm_provider=intent.provider,
                llm_model=intent.model,
                prompt_version=intent.prompt_version,
                skill_version=intent.skill_version,
                llm_call_count=llm_call_count,
                next_action="RETRY_OR_OPERATOR_CHECK",
                customer_message="운영 정보를 확인하지 못했습니다. 잠시 후 다시 시도해 주세요.",
            )
            _append_audit(evaluation_audit, {"stage": "ERROR", "where": "LOOKUP_TOOL", "error_type": type(exc).__name__})
            _append_audit(evaluation_audit, {"stage": "FINAL_RESPONSE", **response.model_dump(mode="json")})
            _record_response_event("lookup_tool_failed", request, response)
            return response
        selected_tools.extend(lookup_tools)
        context.tool_results = tool_results
        _append_audit(
            evaluation_audit,
            {
                "stage": "LOOKUP_RESULTS",
                "executed_tools": list(lookup_tools),
                "tool_results": tool_results,
            },
        )
        try:
            intent = analyze_after_tools(
                request.message,
                context,
                intent,
                provider=llm_provider,
                request_id=request.request_id,
                audit=evaluation_audit,
            )
            llm_call_count += 1
            _append_audit(evaluation_audit, _decision_audit("FOLLOWUP_DECISION", intent))
        except Exception as exc:
            response = AgentResponse(
                status=AgentStatus.ERROR,
                session_id=session.session_id,
                team_id=session.team_id,
                puzzle_id=effective_puzzle_id,
                decision_source="LLM_FOLLOWUP_ERROR",
                reason_codes=[type(exc).__name__],
                selected_tools=selected_tools,
                next_action="RETRY_OR_OPERATOR_CHECK",
                customer_message="운영 상태를 확인했지만 후속 판단 중 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.",
                llm_call_count=llm_call_count,
            )
            _append_audit(
                evaluation_audit,
                {"stage": "ERROR", "where": "FOLLOWUP_LLM", "error_type": type(exc).__name__},
            )
            _append_audit(evaluation_audit, {"stage": "FINAL_RESPONSE", **response.model_dump(mode="json")})
            _record_response_event("llm_followup_failed", request, response)
            return response

        # 반복 lookup 루프는 만들지 않는다. FOLLOWUP이 다시 조회를 요구한 상태에서는
        # 필요한 정보가 아직 부족하므로 action을 실행하지 않는다. 조회 요청만 지운 뒤
        # write를 진행하거나 자동으로 직원을 호출하지 않는다.
        if intent.lookup_tools:
            response = AgentResponse(
                status=AgentStatus.NEED_MORE_INFO,
                session_id=session.session_id,
                team_id=session.team_id,
                puzzle_id=effective_puzzle_id,
                intent=intent.intent,
                emotion=intent.emotion,
                decision_source="FOLLOWUP_LOOKUP_LIMIT_GUARD",
                reason_codes=["FOLLOWUP_LOOKUP_LIMIT_REACHED"],
                selected_tools=selected_tools,
                llm_provider=intent.provider,
                llm_model=intent.model,
                prompt_version=intent.prompt_version,
                skill_version=intent.skill_version,
                llm_call_count=llm_call_count,
                next_action="ASK_CLARIFICATION",
                customer_message=(intent.clarifying_question or "추가 확인이 필요한 상태라 자동 처리를 중단했습니다. 필요한 내용을 조금 더 알려주세요."),
                pending_actions=[AgentActionType.ASK_CLARIFICATION],
                context_notes=list(intent.context_notes) + ["추가 조회 요청은 1회 follow-up 제한으로 실행하지 않음"],
            )
            _append_audit(evaluation_audit, {"stage": "LOOKUP_LIMIT_STOP", "requested_tools": [x.value for x in intent.lookup_tools]})
            _append_audit(evaluation_audit, {"stage": "FINAL_RESPONSE", **response.model_dump(mode="json")})
            _record_response_event("followup_lookup_limit_stop", request, response)
            return response

    actions = list(intent.actions)

    # 여기까지 도달했다는 것은 INITIAL/FOLLOWUP JSON·schema·확정 policy 검증이 모두
    # 통과했다는 뜻이다. 계약 실패에서는 conversation/GM/hint write가 0회여야 하므로
    # 사용자 대화 기록도 이 지점 이후에만 수행한다.
    mcp.record_conversation_turn(session.session_id, "user", request.message, request.request_id)

    # 4) 조회 결과까지 본 뒤에도 정보가 부족하면 부작용 실행 전에 질문한다.
    if intent.needs_clarification or AgentActionType.ASK_CLARIFICATION in actions:
        return _clarification_response(
            request=request,
            session_id=session.session_id,
            team_id=session.team_id,
            puzzle_id=effective_puzzle_id,
            intent=intent,
            selected_tools=selected_tools,
            llm_call_count=llm_call_count,
            evaluation_audit=evaluation_audit,
        )

    completed: list[AgentActionType] = []
    pending: list[AgentActionType] = []
    master_request_ids: list[str] = []
    last_master_request: dict | None = None
    reported_skill_rules = filter_reported_skill_rule_ids(intent.applied_skill_rules)
    reason_codes: list[str] = [intent.reason] + [
        f"LLM_REPORTED_SKILL_RULE:{rule}" for rule in reported_skill_rules
    ]
    hint_text: str | None = None
    hint_strength = None
    answer_offer = None

    # 5) 최종 LLM 행동만 코드 허용 목록/권한/상태 계약 안에서 실행한다.
    for action in actions:
        if action == AgentActionType.REPORT_EQUIPMENT:
            item = mcp.equipment(
                request.session_id,
                request.team_id,
                _staff_handoff_detail(intent),
                f"{request.request_id}:EQUIPMENT",
            )
            completed.append(action)
            selected_tools.append("report_equipment_issue")
            master_request_ids.append(item["request_id"])
            last_master_request = item
            record_event(
                "tool_call",
                {
                    "trace_id": request.request_id,
                    "request_id": request.request_id,
                    "session_id": session.session_id,
                    "tool_name": "report_equipment_issue",
                    "tool_status": "SUCCESS",
                },
            )

        elif action == AgentActionType.REQUEST_GAME_MASTER:
            item = mcp.call_master(
                request.session_id,
                request.team_id,
                "DIRECT_REQUEST",
                f"{request.request_id}:MASTER_REQUEST",
                puzzle_id=effective_puzzle_id,
                summary=_staff_handoff_detail(intent),
            )
            completed.append(action)
            selected_tools.append("request_game_master")
            master_request_ids.append(item["request_id"])
            last_master_request = item
            record_event(
                "tool_call",
                {
                    "trace_id": request.request_id,
                    "request_id": request.request_id,
                    "session_id": session.session_id,
                    "tool_name": "request_game_master",
                    "tool_status": "SUCCESS",
                },
            )

        elif action == AgentActionType.REQUEST_TIME_EXTENSION:
            # 시간 자체는 변경하지 않고 직원 요청으로만 기록한다.
            item = mcp.call_master(
                request.session_id,
                request.team_id,
                "DIRECT_REQUEST",
                f"{request.request_id}:TIME_EXTENSION",
                puzzle_id=effective_puzzle_id,
                summary=_staff_handoff_detail(intent),
            )
            completed.append(action)
            selected_tools.append("request_game_master")
            master_request_ids.append(item["request_id"])
            last_master_request = item
            record_event(
                "tool_call",
                {
                    "trace_id": request.request_id,
                    "request_id": request.request_id,
                    "session_id": session.session_id,
                    "tool_name": "request_game_master",
                    "tool_status": "SUCCESS",
                },
            )

        elif action == AgentActionType.PROVIDE_HINT:
            if not effective_puzzle_id:
                pending.append(AgentActionType.ASK_CLARIFICATION)
                continue

            # support_need의 적절성은 Domain Skill/사람 평가 대상이다.
            # 코드는 승인된 WEAK/STRONG 데이터 경계로만 매핑한다.
            decision = select_approved_hint_strength(
                session=session,
                remaining_time_minutes=context.remaining_time_minutes,
                support_need=intent.support_need,
            )
            reason_codes.extend(decision.reason_codes)
            try:
                hint_text = _get_hint_with_retry(
                    session.session_id,
                    session.team_id,
                    effective_puzzle_id,
                    decision.strength.value,
                    request_id=request.request_id,
                )
            except KeyError:
                item = mcp.call_master(
                    request.session_id,
                    request.team_id,
                    "ABNORMAL_STATE",
                    f"{request.request_id}:APPROVED_HINT_MISSING",
                    puzzle_id=effective_puzzle_id,
                    summary="APPROVED_HINT_DATA_MISSING",
                )
                pending.append(AgentActionType.REQUEST_GAME_MASTER)
                selected_tools.append("request_game_master")
                master_request_ids.append(item["request_id"])
                last_master_request = item
                reason_codes.append("APPROVED_HINT_DATA_MISSING")
                continue
            except (TimeoutError, ConnectionError) as exc:
                response = AgentResponse(
                    status=AgentStatus.ERROR,
                    session_id=session.session_id,
                    team_id=session.team_id,
                    puzzle_id=effective_puzzle_id,
                    intent=intent.intent,
                    emotion=intent.emotion,
                    decision_source="APPROVED_DATA_RETRY_POLICY",
                    reason_codes=reason_codes + ["APPROVED_HINT_LOOKUP_FAILED"],
                    selected_tools=selected_tools + ["get_approved_hint"],
                    llm_provider=intent.provider,
                    llm_model=intent.model,
                    prompt_version=intent.prompt_version,
                    skill_version=intent.skill_version,
                    llm_call_count=llm_call_count,
                    next_action="RETRY_REQUEST",
                    context_notes=intent.context_notes,
                )
                _append_audit(
                    evaluation_audit,
                    {"stage": "ERROR", "where": "APPROVED_HINT_LOOKUP", "error_type": type(exc).__name__},
                )
                _append_audit(evaluation_audit, {"stage": "FINAL_RESPONSE", **response.model_dump(mode="json")})
                _record_response_event("approved_hint_lookup_failed", request, response)
                return response

            event = HintEvent(
                session_id=session.session_id,
                team_id=session.team_id,
                puzzle_id=effective_puzzle_id,
                strength=decision.strength,
                delivered_at=datetime.now(timezone.utc),
                reason_codes=decision.reason_codes,
                idempotency_key=f"{request.request_id}:PROVIDED:{effective_puzzle_id}",
            )
            mcp.record_hint(event)
            record_event(
                "tool_call",
                {
                    "trace_id": request.request_id,
                    "request_id": request.request_id,
                    "session_id": session.session_id,
                    "tool_name": "record_hint_delivery",
                    "tool_status": "SUCCESS",
                },
            )
            selected_tools.extend(["get_approved_hint", "record_hint_delivery"])
            completed.append(action)
            hint_strength = decision.strength

            if intent.support_need == SupportNeed.ANSWER or intent.direct_answer_request:
                answer_offer = create_answer_offer(
                    session.session_id,
                    session.team_id,
                    effective_puzzle_id,
                )
                record_event(
                    "tool_call",
                    {
                        "trace_id": request.request_id,
                        "request_id": request.request_id,
                        "session_id": session.session_id,
                        "tool_name": "create_answer_offer",
                        "tool_status": "SUCCESS",
                    },
                )
                pending.append(AgentActionType.PROVIDE_HINT)

    # 실제 외부 Slack이 아닌 Mock adapter이며 알림 실패가 본 요청을 되돌리지 않는다.
    if master_request_ids and any(
        a in completed for a in {AgentActionType.REPORT_EQUIPMENT, AgentActionType.REQUEST_GAME_MASTER}
    ):
        try:
            slack_notification_adapter.send_master_request_notification(
                last_master_request or {"request_id": master_request_ids[-1]}
            )
        except Exception:
            record_event("slack_notification_failed", {"request_id": master_request_ids[-1]})

    # 6) 부분 처리와 실제 실행 결과를 숨기지 않는다.
    requires_confirmation = answer_offer is not None
    if requires_confirmation and not master_request_ids:
        status = AgentStatus.ANSWER_CONFIRMATION_REQUIRED
    elif len(completed) + len(pending) > 1:
        status = AgentStatus.MULTI_ACTION
    elif hint_text is not None:
        status = AgentStatus.PROVIDE_HINT
    elif master_request_ids:
        status = AgentStatus.MASTER_REQUEST
    elif pending:
        status = AgentStatus.NEED_MORE_INFO
    elif intent.customer_guidance:
        status = AgentStatus.INFORMATION
    else:
        status = AgentStatus.NEED_MORE_INFO

    # LLM 안내는 조회만 한 정보성 응답에서 사용한다. 실제 부작용 실행 결과는 코드가 확인한 사실로 안내한다.
    if not completed and not pending and intent.customer_guidance:
        customer_message = intent.customer_guidance
    else:
        messages: list[str] = []
        if hint_text:
            messages.append("승인된 힌트를 제공할 수 있습니다.")
        if master_request_ids:
            messages.append("직원 확인 요청이 접수되었습니다.")
        if requires_confirmation:
            messages.append("정답 공개 전 사용자 확인이 필요합니다.")
        if pending and not messages:
            messages.append("추가 확인이 필요합니다.")
        customer_message = " ".join(messages) if messages else (intent.customer_guidance or "추가 확인이 필요합니다.")

    if requires_confirmation:
        next_action = "CONFIRM_ANSWER"
    elif master_request_ids and not hint_text:
        next_action = "WAIT_FOR_GAME_MASTER"
    elif status == AgentStatus.INFORMATION:
        next_action = "WAIT_FOR_USER"
    elif pending:
        next_action = "ASK_CLARIFICATION"
    else:
        next_action = "DONE"

    decision_source = f"{intent.provider.upper()}_PLAN"
    if context.tool_results:
        decision_source += "+TOOL_FOLLOWUP"
    decision_source += "+CODE_GUARD"

    _append_audit(
        evaluation_audit,
        {
            "stage": "EXECUTION",
            "completed_actions": [item.value for item in completed],
            "pending_actions": [item.value for item in pending],
            "selected_tools": list(selected_tools),
            "master_request_ids": list(master_request_ids),
            "hint_delivered": hint_text is not None,
            "answer_offer_created": answer_offer is not None,
        },
    )

    response = AgentResponse(
        status=status,
        session_id=session.session_id,
        team_id=session.team_id,
        puzzle_id=effective_puzzle_id,
        intent=intent.intent,
        emotion=intent.emotion,
        hint_strength=hint_strength,
        hint_text=hint_text,
        offer_id=answer_offer["offer_id"] if answer_offer else None,
        offer_expires_at=answer_offer["offer_expires_at"] if answer_offer else None,
        requires_confirmation=requires_confirmation,
        decision_source=decision_source,
        remaining_time_minutes=context.remaining_time_minutes,
        reason_codes=reason_codes,
        selected_tools=selected_tools,
        llm_provider=intent.provider,
        llm_model=intent.model,
        prompt_version=intent.prompt_version,
        skill_version=intent.skill_version,
        llm_call_count=llm_call_count,
        next_action=next_action,
        customer_message=customer_message,
        completed_actions=completed,
        pending_actions=pending,
        master_request_ids=master_request_ids,
        context_notes=intent.context_notes,
    )
    mcp.record_conversation_turn(
        session.session_id,
        "assistant",
        _assistant_turn_text(response),
        request.request_id,
    )
    _append_audit(evaluation_audit, {"stage": "FINAL_RESPONSE", **response.model_dump(mode="json")})
    _record_response_event("agent_request_completed", request, response)
    return response
