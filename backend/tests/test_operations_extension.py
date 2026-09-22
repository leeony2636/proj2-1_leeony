from backend.schemas import AgentRequest, AgentStatus, IntentType
from backend.services.agent_orchestrator import (
    handle_agent_request,
    mcp,
    slack_notification_adapter,
)


def test_time_extension_is_handed_to_game_master_without_timer_change():
    session = mcp.create_session("last_train", "team-time-extension")
    duration_minutes_before = session["duration_minutes"]

    response = handle_agent_request(
        AgentRequest(
            session_id=session["session_id"],
            team_id="team-time-extension",
            message="시간을 더 주면 안 되나요?",
        )
    )

    session_after = mcp.get_session(session["session_id"])
    matching_requests = [
        item
        for item in mcp.master_requests()
        if item["session_id"] == session["session_id"]
    ]

    assert response.status == AgentStatus.MASTER_REQUEST
    assert response.intent == IntentType.TIME_EXTENSION_REQUEST
    assert response.next_action == "WAIT_FOR_GAME_MASTER"
    assert session_after["duration_minutes"] == duration_minutes_before
    assert matching_requests[-1]["reason"] == "TIME_EXTENSION_REQUEST"


def test_equipment_issue_is_recorded_in_mock_slack_without_external_call():
    session = mcp.create_session("last_train", "team-equipment-slack")
    sent_count_before = len(slack_notification_adapter.sent_requests)

    response = handle_agent_request(
        AgentRequest(
            session_id=session["session_id"],
            team_id="team-equipment-slack",
            message="자물쇠를 눌러도 반응이 없어요.",
        )
    )

    assert response.status == AgentStatus.MASTER_REQUEST
    assert response.intent == IntentType.EQUIPMENT_ISSUE
    assert len(slack_notification_adapter.sent_requests) == sent_count_before + 1
    assert (
        slack_notification_adapter.sent_requests[-1]["session_id"]
        == session["session_id"]
    )


def test_mock_slack_failure_does_not_fail_equipment_request(monkeypatch):
    class FailingSlackNotificationAdapter:
        def send_master_request_notification(self, master_request: dict) -> None:
            raise RuntimeError("MOCK_SLACK_FAILURE")

    monkeypatch.setattr(
        "backend.services.agent_orchestrator.slack_notification_adapter",
        FailingSlackNotificationAdapter(),
    )

    session = mcp.create_session("last_train", "team-slack-failure")
    response = handle_agent_request(
        AgentRequest(
            session_id=session["session_id"],
            team_id="team-slack-failure",
            message="자물쇠를 눌러도 반응이 없어요.",
        )
    )

    matching_requests = [
        item
        for item in mcp.master_requests()
        if item["session_id"] == session["session_id"]
    ]

    assert response.status == AgentStatus.MASTER_REQUEST
    assert response.intent == IntentType.EQUIPMENT_ISSUE
    assert matching_requests[-1]["reason"].startswith("EQUIPMENT_ISSUE:")
