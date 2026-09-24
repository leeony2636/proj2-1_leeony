from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import AgentRequest, AgentStatus
from backend.services import agent_orchestrator
from backend.services.context_builder import build_agent_context
from backend.services.llm import _normalize
from backend.services.llm_contract import LLMSchemaValidationError
from backend.services.master_auth import MasterPrincipal, require_game_master_access
from backend.routers import master as master_router
from evals.evaluation_runtime import EvaluationMCPClient, isolated_agent_runtime
from mcp_server.adapters.local_runtime import LocalRuntime
from backend.repositories.memory import MemoryRepository


def _valid_llm_payload() -> dict:
    return {
        "intent": "HINT",
        "intents": ["HINT"],
        "actions": ["PROVIDE_HINT"],
        "lookup_tools": [],
        "emotion": "LOW",
        "needs_clarification": False,
        "clarifying_question": None,
        "reason": "첫 힌트 요청",
        "direct_answer_request": False,
        "strong_hint_request": False,
        "frustration_high": False,
        "support_need": "STANDARD",
        "customer_guidance": None,
        "staff_facts": [],
        "staff_attempts": [],
        "staff_unknowns": [],
        "applied_skill_rules": [],
        "context_notes": [],
    }


def _authorized_principal() -> MasterPrincipal:
    return MasterPrincipal(subject="gm-test", role="game_master", auth_source="TEST")


def test_valid_llm_json_is_execution_candidate_only_after_strict_validation():
    result = _normalize(_valid_llm_payload(), "test", "fixed", "2026-09-22.v3")
    assert result.intent.value == "HINT"
    assert [item.value for item in result.actions] == ["PROVIDE_HINT"]


def test_initial_schema_failure_has_zero_mcp_writes(monkeypatch):
    with isolated_agent_runtime() as client:
        session = client.create_session("last_train", "team-schema-stop")

        def invalid_initial(*args, **kwargs):
            payload = _valid_llm_payload()
            payload["direct_answer_request"] = "false"
            return _normalize(payload, "test", "fixed", "2026-09-22.v3")

        monkeypatch.setattr(agent_orchestrator, "analyze_user_request", invalid_initial)
        response = agent_orchestrator.handle_agent_request(
            AgentRequest(
                session_id=session["session_id"],
                team_id="team-schema-stop",
                message="힌트 주세요",
            ),
            llm_provider="baseline",
        )

        assert response.status == AgentStatus.ERROR
        assert client.master_request_status(session["session_id"], "team-schema-stop") == []
        assert client.get_history(session["session_id"], "team-schema-stop", session["current_puzzle_id"]) == []
        assert client.get_conversation_history(session["session_id"]) == []


def test_missing_customer_puzzle_id_uses_server_current_puzzle():
    client = EvaluationMCPClient()
    session = client.create_session("last_train", "team-current")
    _, context = build_agent_context(
        client,
        session_id=session["session_id"],
        team_id="team-current",
        requested_puzzle_id=None,
    )
    assert context.requested_puzzle_id == session["current_puzzle_id"]


def test_mismatched_customer_puzzle_id_stops_before_state_change():
    client = EvaluationMCPClient()
    session = client.create_session("last_train", "team-mismatch")
    before = client.master_request_status(session["session_id"], "team-mismatch")
    with pytest.raises(ValueError, match="PUZZLE_ID_MISMATCH"):
        build_agent_context(
            client,
            session_id=session["session_id"],
            team_id="team-mismatch",
            requested_puzzle_id="train-p02",
        )
    after = client.master_request_status(session["session_id"], "team-mismatch")
    assert before == after == []


def test_other_team_session_pair_is_rejected():
    client = EvaluationMCPClient()
    session = client.create_session("last_train", "team-owner-hardening")
    with pytest.raises(PermissionError, match="TEAM_SESSION_MISMATCH"):
        client.get_agent_session(session["session_id"], "team-other-hardening")


def test_game_master_missing_auth_is_401_and_queue_unchanged(monkeypatch):
    monkeypatch.setenv("APP_ENV", "development")
    monkeypatch.delenv("GM_AUTH_BYPASS_LOCAL", raising=False)
    app.dependency_overrides.clear()
    before = len(master_router.mcp.master_requests())
    response = TestClient(app).get("/api/master/requests")
    after = len(master_router.mcp.master_requests())
    assert response.status_code == 401
    assert before == after


def test_game_master_viewer_role_is_403():
    app.dependency_overrides[require_game_master_access] = lambda: MasterPrincipal(
        subject="viewer-test", role="viewer", auth_source="TEST"
    )
    try:
        response = TestClient(app).get("/api/master/requests")
        # Overriding require_game_master_access itself bypasses its role check, so verify the
        # real dependency by overriding its child instead in a separate request below.
        assert response.status_code == 200
    finally:
        app.dependency_overrides.clear()

    from backend.services.master_auth import resolve_master_principal
    app.dependency_overrides[resolve_master_principal] = lambda: MasterPrincipal(
        subject="viewer-test", role="viewer", auth_source="TEST"
    )
    try:
        response = TestClient(app).get("/api/master/requests")
        assert response.status_code == 403
    finally:
        app.dependency_overrides.clear()


def test_game_master_authenticated_body_validation_is_422():
    app.dependency_overrides[require_game_master_access] = _authorized_principal
    try:
        response = TestClient(app).post("/api/master/requests/not-a-real-id/acknowledge", json={})
        assert response.status_code == 422
    finally:
        app.dependency_overrides.clear()


def test_game_master_invalid_state_transition_is_409():
    session = master_router.mcp.create_session("last_train", "team-gm-conflict")
    item = master_router.mcp.call_master(
        session["session_id"], "team-gm-conflict", "DIRECT_REQUEST", "gm-conflict-key", summary="테스트 요청"
    )
    app.dependency_overrides[require_game_master_access] = _authorized_principal
    try:
        response = TestClient(app).post(
            f"/api/master/requests/{item['request_id']}/resolve",
            json={"operator_id": "self-claimed", "note": "skip ack"},
        )
        assert response.status_code == 409
        current = next(row for row in master_router.mcp.master_requests() if row["request_id"] == item["request_id"])
        assert current["status"] == "OPEN"
    finally:
        app.dependency_overrides.clear()


def test_production_cannot_enable_local_game_master_bypass(monkeypatch):
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("GM_AUTH_BYPASS_LOCAL", "true")
    app.dependency_overrides.clear()
    response = TestClient(app).get("/api/master/requests")
    assert response.status_code == 401
    assert response.json()["detail"] == "GM_AUTH_MISCONFIGURED"


def test_legacy_unknown_reason_is_not_guessed_from_substring():
    repo = MemoryRepository()
    runtime = LocalRuntime(repo)
    session = runtime.create_session("last_train", "team-legacy")
    repo.save_master_request(
        {
            "request_id": "legacy-1",
            "session_id": session.session_id,
            "team_id": "team-legacy",
            "reason": "lock seems broken but unverified",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "OPEN",
            "deduplicated": False,
        }
    )
    row = runtime.get_master_requests_for_session(session.session_id, "team-legacy")[0]
    assert row["reason"] == "UNKNOWN"
    assert row["summary"] == "lock seems broken but unverified"
    assert row["legacy_reason_unmapped"] is True


def test_new_master_write_keeps_enum_reason_and_summary_separate():
    runtime = LocalRuntime(MemoryRepository())
    session = runtime.create_session("last_train", "team-reason-v2")
    row = runtime.request_game_master(
        session.session_id,
        "team-reason-v2",
        "ABNORMAL_STATE",
        "reason-v2-key",
        summary="고객 사실: 자물쇠가 반응하지 않는다고 말함 | 미확인: 실제 고장 여부",
    )
    assert row["reason"] == "ABNORMAL_STATE"
    assert row["summary"].startswith("고객 사실:")
    assert row["legacy_reason_unmapped"] is False
