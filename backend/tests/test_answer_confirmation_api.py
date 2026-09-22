from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import HintEvent, HintStrength
from backend.services.answer_vault import create_answer_offer, confirm_answer
from backend.services.mcp_client import MCPClient


client = TestClient(app)


def _strong_session(team_id: str) -> dict:
    mcp = MCPClient()
    session = mcp.create_session("last_train", team_id)
    mcp.record_hint(
        HintEvent(
            session_id=session["session_id"],
            team_id=team_id,
            puzzle_id=session["current_puzzle_id"],
            strength=HintStrength.STRONG,
            delivered_at=datetime.now(timezone.utc),
            reason_codes=["TEST_STRONG"],
        )
    )
    return session


def test_answer_offer_is_one_time_and_requires_explicit_confirmation():
    session = _strong_session("team-confirm-api")
    offer = create_answer_offer(
        session["session_id"],
        "team-confirm-api",
        session["current_puzzle_id"],
    )

    result = confirm_answer(
        session["session_id"],
        "team-confirm-api",
        session["current_puzzle_id"],
        offer["offer_id"],
    )

    assert result["policy"] == "USER_EXPLICIT_CONFIRMATION"
    assert result["answer"]

    with pytest.raises(PermissionError, match="ANSWER_OFFER_ALREADY_CONSUMED"):
        confirm_answer(
            session["session_id"],
            "team-confirm-api",
            session["current_puzzle_id"],
            offer["offer_id"],
        )


def test_post_answers_confirm_uses_offer_id():
    session = _strong_session("team-confirm-route")
    offer = create_answer_offer(
        session["session_id"],
        "team-confirm-route",
        session["current_puzzle_id"],
    )

    response = client.post(
        "/api/answers/confirm",
        json={
            "session_id": session["session_id"],
            "team_id": "team-confirm-route",
            "puzzle_id": session["current_puzzle_id"],
            "offer_id": offer["offer_id"],
        },
    )

    assert response.status_code == 200
    assert response.json()["policy"] == "USER_EXPLICIT_CONFIRMATION"


def test_legacy_get_reveal_endpoint_is_not_public():
    assert "/api/answers/reveal" not in client.app.openapi()["paths"]
