import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.services.mcp_client import MCPClient


client = TestClient(app)


def _request(team_id: str = "team-master-lifecycle") -> dict:
    mcp = MCPClient()
    session = mcp.create_session("last_train", team_id)
    return mcp.call_master(
        session["session_id"],
        team_id,
        "CUSTOMER_REQUEST",
        f"master-lifecycle:{team_id}",
    )


def test_master_request_uses_documented_open_lifecycle():
    item = _request()
    assert item["status"] == "OPEN"

    acknowledged = MCPClient().update_master_request(
        item["request_id"],
        "ACKNOWLEDGED",
        "gm-001",
        "확인 중",
        "master-action:ack-001",
    )
    assert acknowledged["status"] == "ACKNOWLEDGED"
    assert acknowledged["operator_id"] == "gm-001"

    resolved = MCPClient().update_master_request(
        item["request_id"],
        "RESOLVED",
        "gm-001",
        "고객에게 안내 완료",
        "master-action:resolve-001",
    )
    assert resolved["status"] == "RESOLVED"


def test_master_request_rejects_invalid_transition():
    item = _request("team-master-invalid")

    with pytest.raises(ValueError, match="MASTER_REQUEST_INVALID_TRANSITION"):
        MCPClient().update_master_request(
            item["request_id"],
            "RESOLVED",
            "gm-002",
            "확인 없이 해결",
            "master-action:invalid-001",
        )


def test_master_request_lifecycle_endpoint_is_available():
    item = _request("team-master-route")
    response = client.post(
        f"/api/master/requests/{item['request_id']}/acknowledge",
        json={"operator_id": "gm-route", "note": "확인"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ACKNOWLEDGED"


def test_master_request_rejects_unknown_session_and_wrong_team():
    mcp = MCPClient()
    session = mcp.create_session("last_train", "team-master-owner")

    with pytest.raises(KeyError, match="SESSION_NOT_FOUND"):
        mcp.call_master("unknown-session", "team-master-owner", "CUSTOMER_REQUEST")

    with pytest.raises(PermissionError, match="TEAM_SESSION_MISMATCH"):
        mcp.call_master(session["session_id"], "team-master-other", "CUSTOMER_REQUEST")


def test_master_action_requires_operator_id():
    item = _request("team-master-operator")
    response = client.post(
        f"/api/master/requests/{item['request_id']}/acknowledge",
        json={"operator_id": "", "note": "확인"},
    )

    assert response.status_code == 422
