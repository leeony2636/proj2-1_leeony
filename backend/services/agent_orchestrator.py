from datetime import datetime, timezone

from backend.schemas import (
    AgentRequest,
    AgentResponse,
    AgentStatus,
    HintEvent,
    IntentType,
    SessionState,
)
from backend.services.hint_decision import decide_hint_strength
from backend.services.langfuse_service import record_event
from backend.services.llm import analyze_user_request
from backend.services.mcp_client import MCPClient


mcp = MCPClient()


def _remaining_time_minutes(session: SessionState) -> float:
    elapsed = (
        datetime.now(timezone.utc) - session.started_at
    ).total_seconds() / 60
    return max(session.duration_minutes - elapsed, 0.0)


def handle_agent_request(request: AgentRequest) -> AgentResponse:
    # 1) LLM/baseline은 자연어를 구조화한다. 최종 강도는 여기서 정하지 않는다.
    intent = analyze_user_request(request.message, request.puzzle_id)

    # 2) 장비 이상/직원 직접 호출은 일반 힌트 경로로 처리하지 않는다.
    if intent.intent in {IntentType.EQUIPMENT_ISSUE, IntentType.MASTER_REQUEST}:
        if intent.intent == IntentType.EQUIPMENT_ISSUE:
            mcp.equipment(request.session_id, request.team_id, intent.reason)
        else:
            mcp.call_master(request.session_id, request.team_id, intent.reason)

        response = AgentResponse(
            status=AgentStatus.MASTER_REQUEST,
            session_id=request.session_id,
            team_id=request.team_id,
            puzzle_id=request.puzzle_id,
            intent=intent.intent,
            emotion=intent.emotion,
            decision_source="POLICY_HANDOFF",
            reason_codes=[intent.reason],
            selected_tools=intent.recommended_tools,
            llm_provider=intent.provider,
            llm_model=intent.model,
            next_action="WAIT_FOR_GAME_MASTER",
        )
        record_event("master_request", response.model_dump(mode="json"))
        return response

    # 3) 정보가 부족하면 임의로 힌트를 만들지 않는다.
    if intent.needs_clarification or not request.puzzle_id:
        response = AgentResponse(
            status=AgentStatus.NEED_MORE_INFO,
            session_id=request.session_id,
            team_id=request.team_id,
            puzzle_id=request.puzzle_id,
            intent=intent.intent,
            emotion=intent.emotion,
            decision_source="POLICY_CLARIFICATION",
            reason_codes=[intent.reason],
            selected_tools=intent.recommended_tools,
            llm_provider=intent.provider,
            llm_model=intent.model,
            next_action="ASK_CURRENT_PUZZLE",
        )
        record_event("need_more_info", response.model_dump(mode="json"))
        return response

    # 4) 세션/팀/시간 검증.
    session = SessionState.model_validate(mcp.get_session(request.session_id))
    if session.team_id != request.team_id:
        raise ValueError("TEAM_SESSION_MISMATCH")

    remaining_time = _remaining_time_minutes(session)
    if session.is_closed or remaining_time <= 0:
        return AgentResponse(
            status=AgentStatus.CLOSED,
            session_id=session.session_id,
            team_id=session.team_id,
            puzzle_id=request.puzzle_id,
            intent=intent.intent,
            emotion=intent.emotion,
            decision_source="SESSION_POLICY",
            selected_tools=intent.recommended_tools,
            llm_provider=intent.provider,
            llm_model=intent.model,
            next_action="SESSION_CLOSED",
        )

    # 5) 미래/다른 순서 퍼즐은 스포일러 방지를 위해 GM 경로로 전환한다.
    if session.current_puzzle_id and request.puzzle_id != session.current_puzzle_id:
        reason = "PUZZLE_SEQUENCE_MISMATCH"
        mcp.call_master(request.session_id, request.team_id, reason)
        response = AgentResponse(
            status=AgentStatus.MASTER_REQUEST,
            session_id=session.session_id,
            team_id=session.team_id,
            puzzle_id=request.puzzle_id,
            intent=intent.intent,
            emotion=intent.emotion,
            decision_source="SPOILER_POLICY_HANDOFF",
            reason_codes=[reason],
            selected_tools=["get_game_session", "request_game_master"],
            llm_provider=intent.provider,
            llm_model=intent.model,
            next_action="WAIT_FOR_GAME_MASTER",
        )
        record_event("spoiler_guard_handoff", response.model_dump(mode="json"))
        return response

    # 6) 상태/이력을 조회한다.
    mcp.get_puzzle(session.theme_id, request.puzzle_id)
    mcp.get_history(session.session_id, request.puzzle_id)

    # 7) 최종 WEAK/STRONG은 deterministic code가 결정한다.
    decision = decide_hint_strength(
        session=session,
        remaining_time_minutes=remaining_time,
        direct_answer_request=intent.direct_answer_request,
        strong_hint_request=intent.strong_hint_request,
        frustration_high=intent.frustration_high,
    )

    # 8) LLM이 새 힌트를 생성하지 않고 승인된 HintStep만 가져온다.
    hint_text = mcp.get_hint(
        session.theme_id,
        request.puzzle_id,
        decision.strength.value,
    )

    event = HintEvent(
        session_id=session.session_id,
        team_id=session.team_id,
        puzzle_id=request.puzzle_id,
        strength=decision.strength,
        delivered_at=datetime.now(timezone.utc),
        reason_codes=decision.reason_codes,
    )
    mcp.record_hint(event)

    strong = decision.strength.value == "STRONG"
    response = AgentResponse(
        status=AgentStatus.PROVIDE_HINT,
        session_id=session.session_id,
        team_id=session.team_id,
        puzzle_id=request.puzzle_id,
        intent=intent.intent,
        emotion=intent.emotion,
        hint_strength=decision.strength,
        hint_text=hint_text,
        decision_source="CODE_RULE",
        answer_available=strong,
        answer_reveal_url=(
            f"/api/answers/reveal?session_id={session.session_id}"
            f"&team_id={session.team_id}&puzzle_id={request.puzzle_id}"
            if strong
            else None
        ),
        remaining_time_minutes=decision.remaining_time_minutes,
        reason_codes=decision.reason_codes,
        selected_tools=intent.recommended_tools
        + ["get_approved_hint", "record_hint_delivery"],
        llm_provider=intent.provider,
        llm_model=intent.model,
        next_action="RETRY_PUZZLE",
    )
    record_event("hint_delivered", response.model_dump(mode="json"))
    return response
