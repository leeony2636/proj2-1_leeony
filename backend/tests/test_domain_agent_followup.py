from datetime import datetime, timezone

from backend.schemas import (
    AgentActionType,
    AgentRequest,
    AgentStatus,
    HintEvent,
    HintStrength,
    IntentResult,
    IntentType,
    LookupToolType,
    SupportNeed,
)
from backend.services import agent_orchestrator
from backend.services.context_builder import build_agent_context


def _intent(**overrides):
    data = dict(
        intent=IntentType.UNCLEAR,
        actions=[],
        reason="test decision",
        provider="test-llm",
        model="fake",
        prompt_version="test-prompt",
        skill_version="2026-09-22.v3",
    )
    data.update(overrides)
    return IntentResult(**data)


def test_domain_skill_is_real_llm_context_and_unconfirmed_rules_are_separate():
    session = agent_orchestrator.mcp.create_session("last_train", "team-skill-context")
    _, context = build_agent_context(
        agent_orchestrator.mcp,
        session_id=session["session_id"],
        team_id="team-skill-context",
        requested_puzzle_id=None,
    )

    assert context.domain_skill["version"] == "2026-09-22.v3"
    active_ids = {item["id"] for item in context.domain_skill["llm_guidance"]}
    boundary_ids = {item["id"] for item in context.domain_skill["confirmed_boundaries"]}
    assert "EQUIPMENT_AMBIGUITY" in active_ids
    assert "POSITION_CONFUSION_SUPPORT" in active_ids
    assert "PUZZLE_POSITION_METADATA_PRIVATE" in boundary_ids
    assert context.domain_skill["visibility_legend"]["INTERNAL_ONLY"]
    assert "자기보고" in context.domain_skill["reporting_semantics"]["applied_skill_rules"]
    assert "NUMERIC_HINT_STRENGTH_RULE" in context.domain_skill["unconfirmed_policy_ids"]
    assert all(item["id"] != "NUMERIC_HINT_STRENGTH_RULE" for item in context.domain_skill["llm_guidance"])


def test_master_status_lookup_changes_followup_without_duplicate_request(monkeypatch):
    session = agent_orchestrator.mcp.create_session("last_train", "team-master-followup")
    existing = agent_orchestrator.mcp.call_master(
        session["session_id"],
        "team-master-followup",
        "고객 사실: 직원 호출 요청",
        "existing-master-request",
    )

    def fake_initial(message, context, **_):
        return _intent(
            intent=IntentType.MASTER_REQUEST,
            lookup_tools=[LookupToolType.GET_MASTER_REQUEST_STATUS],
            reason="이전 직원 요청 상태 확인 필요",
            applied_skill_rules=["FOLLOWUP_CONTEXT"],
        )

    def fake_followup(message, context, previous, **_):
        rows = context.tool_results["get_master_request_status"]
        assert rows[0]["request_id"] == existing["request_id"]
        assert rows[0]["status"] == "OPEN"
        return _intent(
            intent=IntentType.MASTER_REQUEST,
            actions=[],
            reason="기존 요청이 아직 OPEN이라 중복 접수하지 않음",
            customer_guidance="기존 직원 요청이 아직 접수 상태입니다. 새 요청을 중복으로 만들지 않고 현재 요청을 기준으로 안내드릴게요.",
            applied_skill_rules=["FOLLOWUP_CONTEXT"],
        )

    monkeypatch.setattr(agent_orchestrator, "analyze_user_request", fake_initial)
    monkeypatch.setattr(agent_orchestrator, "analyze_after_tools", fake_followup)

    response = agent_orchestrator.handle_agent_request(
        AgentRequest(
            session_id=session["session_id"],
            team_id="team-master-followup",
            message="아까 직원 불렀는데 아직 안 왔어요.",
        )
    )

    same_session = agent_orchestrator.mcp.master_request_status(
        session["session_id"], "team-master-followup"
    )
    assert response.status == AgentStatus.INFORMATION
    assert response.llm_call_count == 2
    assert "get_master_request_status" in response.selected_tools
    assert len(same_session) == 1
    assert same_session[0]["request_id"] == existing["request_id"]


def test_hint_history_result_can_change_followup_to_clarification(monkeypatch):
    session = agent_orchestrator.mcp.create_session("last_train", "team-hint-followup")
    puzzle_id = session["current_puzzle_id"]
    agent_orchestrator.mcp.record_hint(
        HintEvent(
            session_id=session["session_id"],
            team_id="team-hint-followup",
            puzzle_id=puzzle_id,
            strength=HintStrength.WEAK,
            delivered_at=datetime.now(timezone.utc),
            reason_codes=["TEST_PREVIOUS_HINT"],
            idempotency_key="previous-hint",
        )
    )

    def fake_initial(message, context, **_):
        assert "hint_history" not in context.model_dump()
        return _intent(
            intent=IntentType.HINT,
            lookup_tools=[LookupToolType.GET_HINT_HISTORY],
            reason="이전 힌트 사용 여부 확인 필요",
            applied_skill_rules=["FOLLOWUP_CONTEXT", "EQUIPMENT_AMBIGUITY"],
        )

    def fake_followup(message, context, previous, **_):
        assert len(context.tool_results["get_hint_history"]) == 1
        return _intent(
            intent=IntentType.UNCLEAR,
            actions=[AgentActionType.ASK_CLARIFICATION],
            needs_clarification=True,
            clarifying_question="힌트대로 시도했을 때 번호는 맞았는데 자물쇠만 열리지 않은 건가요?",
            reason="이전 힌트 제공은 확인됐지만 풀이 문제와 장비 문제를 아직 구분할 수 없음",
            applied_skill_rules=["EQUIPMENT_AMBIGUITY", "CLARIFY_WHEN_NEEDED"],
        )

    monkeypatch.setattr(agent_orchestrator, "analyze_user_request", fake_initial)
    monkeypatch.setattr(agent_orchestrator, "analyze_after_tools", fake_followup)
    before = len(agent_orchestrator.mcp.master_request_status(session["session_id"], "team-hint-followup"))

    response = agent_orchestrator.handle_agent_request(
        AgentRequest(
            session_id=session["session_id"],
            team_id="team-hint-followup",
            message="아까 힌트대로 했는데 안 열려요.",
        )
    )

    after = len(agent_orchestrator.mcp.master_request_status(session["session_id"], "team-hint-followup"))
    assert response.status == AgentStatus.NEED_MORE_INFO
    assert response.llm_call_count == 2
    assert response.customer_message.startswith("힌트대로 시도했을 때")
    assert before == after
    assert AgentActionType.REPORT_EQUIPMENT not in response.completed_actions


def test_ambiguous_hint_and_lock_issue_does_not_force_two_actions(monkeypatch):
    session = agent_orchestrator.mcp.create_session("last_train", "team-ambiguous")

    def fake_initial(message, context, **_):
        return _intent(
            intent=IntentType.UNCLEAR,
            actions=[AgentActionType.ASK_CLARIFICATION],
            needs_clarification=True,
            clarifying_question="힌트가 필요한 문제와 반응하지 않는 자물쇠가 같은 문제인가요?",
            reason="독립 복합 요청인지 동일 문제의 원인 구분인지 불명확",
            applied_skill_rules=["EQUIPMENT_AMBIGUITY", "CLARIFY_WHEN_NEEDED"],
        )

    monkeypatch.setattr(agent_orchestrator, "analyze_user_request", fake_initial)
    response = agent_orchestrator.handle_agent_request(
        AgentRequest(
            session_id=session["session_id"],
            team_id="team-ambiguous",
            message="힌트도 필요하고 자물쇠가 반응하지 않아요.",
        )
    )

    assert response.status == AgentStatus.NEED_MORE_INFO
    assert response.completed_actions == []
    assert agent_orchestrator.mcp.master_request_status(session["session_id"], "team-ambiguous") == []


def test_staff_handoff_keeps_fact_attempt_unknown_separate(monkeypatch):
    session = agent_orchestrator.mcp.create_session("last_train", "team-staff-summary")

    def fake_initial(message, context, **_):
        return _intent(
            intent=IntentType.EQUIPMENT_ISSUE,
            actions=[AgentActionType.REPORT_EQUIPMENT],
            reason="장비 점검 요청",
            staff_facts=["고객이 자물쇠가 반응하지 않는다고 말함"],
            staff_attempts=["승인 힌트대로 번호를 입력했다고 말함"],
            staff_unknowns=["번호 입력이 정확했는지는 미확인"],
            applied_skill_rules=["STAFF_HANDOFF_FACTS"],
        )

    monkeypatch.setattr(agent_orchestrator, "analyze_user_request", fake_initial)
    response = agent_orchestrator.handle_agent_request(
        AgentRequest(
            session_id=session["session_id"],
            team_id="team-staff-summary",
            message="번호 넣었는데 자물쇠가 반응이 없어요.",
        )
    )

    request_row = agent_orchestrator.mcp.master_request_status(
        session["session_id"], "team-staff-summary"
    )[0]
    assert response.status == AgentStatus.MASTER_REQUEST
    assert "고객 사실:" in request_row["reason"]
    assert "고객 시도:" in request_row["reason"]
    assert "미확인:" in request_row["reason"]
    assert "LLM_REPORTED_SKILL_RULE:STAFF_HANDOFF_FACTS" in response.reason_codes


def test_master_request_status_is_session_and_team_scoped():
    a = agent_orchestrator.mcp.create_session("last_train", "team-scope-a")
    b = agent_orchestrator.mcp.create_session("last_train", "team-scope-b")
    agent_orchestrator.mcp.call_master(a["session_id"], "team-scope-a", "A", "scope-a")
    agent_orchestrator.mcp.call_master(b["session_id"], "team-scope-b", "B", "scope-b")

    a_rows = agent_orchestrator.mcp.master_request_status(a["session_id"], "team-scope-a")
    b_rows = agent_orchestrator.mcp.master_request_status(b["session_id"], "team-scope-b")

    assert {row["reason"] for row in a_rows} == {"A"}
    assert {row["reason"] for row in b_rows} == {"B"}
