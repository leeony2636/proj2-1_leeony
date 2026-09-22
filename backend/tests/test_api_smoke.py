from fastapi.testclient import TestClient

from backend.main import app


client = TestClient(app)


def test_p0_customer_flow_reaches_hint_and_master_endpoints():
    health = client.get("/health")
    assert health.status_code == 200

    session_response = client.post(
        "/api/sessions",
        json={"theme_id": "last_train", "team_id": "team-api-smoke"},
    )
    assert session_response.status_code == 200
    session = session_response.json()["session"]

    hint_response = client.post(
        "/api/agent",
        json={
            "session_id": session["session_id"],
            "team_id": session["team_id"],
            "puzzle_id": session["current_puzzle_id"],
            "message": "힌트 주세요",
        },
    )
    assert hint_response.status_code == 200
    assert hint_response.json()["status"] == "PROVIDE_HINT"

    master_response = client.get("/api/master/requests")
    assert master_response.status_code == 200
    assert "requests" in master_response.json()


def test_agent_rejects_unknown_session_without_guessing_hint():
    response = client.post(
        "/api/agent",
        json={
            "session_id": "unknown-session",
            "team_id": "team-api-smoke",
            "puzzle_id": "train-p01",
            "message": "힌트 주세요",
        },
    )

    assert response.status_code == 404
    assert "SESSION_NOT_FOUND" in response.json()["detail"]
