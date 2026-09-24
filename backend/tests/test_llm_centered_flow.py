from backend.schemas import (
    AgentActionType,
    AgentRequest,
    AgentStatus,
    EmotionSignal,
    IntentResult,
    IntentType,
    SupportNeed,
)
from backend.services import agent_orchestrator


def test_compound_request_executes_hint_and_equipment_handoff(monkeypatch):
    session = agent_orchestrator.mcp.create_session("last_train", "team-compound")

    def fake_llm(message, context, **_):
        assert context.current_puzzle_id == session["current_puzzle_id"]
        assert context.puzzle_context is not None
        return IntentResult(
            intent=IntentType.HINT,
            intents=[IntentType.HINT, IntentType.EQUIPMENT_ISSUE],
            actions=[AgentActionType.PROVIDE_HINT, AgentActionType.REPORT_EQUIPMENT],
            emotion=EmotionSignal.MEDIUM,
            reason="힌트 요청과 장비 이상이 함께 있음",
            support_need=SupportNeed.STANDARD,
            staff_facts=["현재 퍼즐의 자물쇠가 반응하지 않는다고 고객이 보고함"],
            staff_unknowns=["실제 장비 고장 여부는 미확인"],
            context_notes=["현재 퍼즐 맥락 사용"],
            provider="test-llm",
            model="fake",
        )

    monkeypatch.setattr(agent_orchestrator, "analyze_user_request", fake_llm)
    response = agent_orchestrator.handle_agent_request(
        AgentRequest(
            session_id=session["session_id"],
            team_id="team-compound",
            message="힌트도 필요하고 자물쇠가 반응이 없어요",
        )
    )

    assert response.status == AgentStatus.MULTI_ACTION
    assert response.hint_text
    assert AgentActionType.PROVIDE_HINT in response.completed_actions
    assert AgentActionType.REPORT_EQUIPMENT in response.completed_actions
    assert response.master_request_ids


def test_recent_turns_are_added_to_next_llm_context(monkeypatch):
    session = agent_orchestrator.mcp.create_session("last_train", "team-context")
    seen_turn_counts = []

    def fake_llm(message, context, **_):
        seen_turn_counts.append(len(context.recent_turns))
        return IntentResult(
            intent=IntentType.HINT,
            actions=[AgentActionType.PROVIDE_HINT],
            reason="현재 퍼즐 힌트 요청",
            support_need=SupportNeed.STANDARD,
            provider="test-llm",
            model="fake",
        )

    monkeypatch.setattr(agent_orchestrator, "analyze_user_request", fake_llm)
    for text in ["힌트 하나 주세요", "아까 그거보다 조금 더 도와줘"]:
        agent_orchestrator.handle_agent_request(
            AgentRequest(
                session_id=session["session_id"],
                team_id="team-context",
                message=text,
            )
        )

    assert seen_turn_counts[0] == 0
    assert seen_turn_counts[1] >= 2  # 첫 요청의 user/assistant turn

