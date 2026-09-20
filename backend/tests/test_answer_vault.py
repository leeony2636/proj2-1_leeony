from datetime import datetime, timezone

import pytest

from backend.schemas import HintEvent, HintStrength
from backend.services.answer_vault import reveal_answer
from backend.services.mcp_client import MCPClient


def test_answer_vault_requires_strong_hint_before_reveal():
    mcp = MCPClient()
    session = mcp.create_session("last_train", "team-vault-test")
    session_id = session["session_id"]
    puzzle_id = session["current_puzzle_id"]

    with pytest.raises(PermissionError):
        reveal_answer(session_id, "team-vault-test", puzzle_id)

    mcp.record_hint(
        HintEvent(
            session_id=session_id,
            team_id="team-vault-test",
            puzzle_id=puzzle_id,
            strength=HintStrength.STRONG,
            delivered_at=datetime.now(timezone.utc),
            reason_codes=["TEST_STRONG"],
        )
    )

    result = reveal_answer(session_id, "team-vault-test", puzzle_id)
    assert result["puzzle_id"] == puzzle_id
    assert result["policy"] == "USER_EXPLICIT_REVEAL_AFTER_STRONG"
    assert result["answer"]
