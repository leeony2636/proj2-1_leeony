import unittest

from backend.schemas import AgentRequest, AgentStatus
from backend.services.agent_orchestrator import handle_agent_request, mcp


class AccessPolicyTests(unittest.TestCase):
    def test_agent_rejects_team_mismatch_before_hint_lookup(self):
        # 수정 사유: P0에서는 session_id와 team_id 조합을 최소 권한 경계로 사용한다.
        session = mcp.create_session("last_train", "team-owner")
        request = AgentRequest(
            session_id=session["session_id"],
            team_id="team-other",
            puzzle_id=session["current_puzzle_id"],
            message="힌트 주세요",
        )

        with self.assertRaisesRegex(PermissionError, "TEAM_SESSION_MISMATCH"):
            handle_agent_request(request)

    def test_closed_session_cannot_receive_hint(self):
        session = mcp.create_session("last_train", "team-closed")
        for puzzle_id in [f"train-p{i:02d}" for i in range(1, 14)]:
            mcp.solve(session["session_id"], puzzle_id)

        response = handle_agent_request(
            AgentRequest(
                session_id=session["session_id"],
                team_id="team-closed",
                puzzle_id="train-p01",
                message="힌트 주세요",
            )
        )

        self.assertEqual(response.status, AgentStatus.CLOSED)
        self.assertIsNone(response.hint_text)

    def test_future_puzzle_request_is_blocked_without_side_effect(self):
        session = mcp.create_session("last_train", "team-future")
        before = len(mcp.master_requests())
        with self.assertRaisesRegex(ValueError, "PUZZLE_ID_MISMATCH"):
            handle_agent_request(
                AgentRequest(
                    session_id=session["session_id"],
                    team_id="team-future",
                    puzzle_id="train-p02",
                    message="2번 퍼즐 힌트 주세요",
                )
            )
        self.assertEqual(len(mcp.master_requests()), before)


if __name__ == "__main__":
    unittest.main()
