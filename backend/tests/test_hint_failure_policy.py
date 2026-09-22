import unittest
from unittest.mock import patch

from backend.schemas import AgentRequest, AgentStatus
from backend.services import agent_orchestrator


class HintFailurePolicyTests(unittest.TestCase):
    def _request(self, team_id: str) -> AgentRequest:
        session = agent_orchestrator.mcp.create_session("last_train", team_id)
        return AgentRequest(
            session_id=session["session_id"],
            team_id=team_id,
            puzzle_id=session["current_puzzle_id"],
            message="힌트 주세요",
        )

    def test_missing_approved_hint_is_handed_to_game_master(self):
        # 수정 사유: 도메인 승인 데이터 누락은 시스템 오류가 아니라 운영 확인 대상이다.
        request = self._request("team-hint-missing")
        with patch.object(
            agent_orchestrator.mcp,
            "get_hint",
            side_effect=KeyError("APPROVED_HINT_NOT_FOUND:last_train:train-p01:WEAK"),
        ):
            response = agent_orchestrator.handle_agent_request(request)

        self.assertEqual(response.status, AgentStatus.MASTER_REQUEST)
        self.assertIn("APPROVED_HINT_DATA_MISSING", response.reason_codes)
        self.assertIsNone(response.hint_text)

    def test_transient_hint_lookup_failure_is_retried_then_returns_error(self):
        # 수정 사유: 일시 장애는 한 번 재시도하되 승인되지 않은 대체 힌트는 만들지 않는다.
        request = self._request("team-hint-transient")
        with patch.object(
            agent_orchestrator.mcp,
            "get_hint",
            side_effect=TimeoutError("MCP_TIMEOUT"),
        ) as get_hint:
            response = agent_orchestrator.handle_agent_request(request)

        self.assertEqual(response.status, AgentStatus.ERROR)
        self.assertIn("APPROVED_HINT_LOOKUP_FAILED", response.reason_codes)
        self.assertIsNone(response.hint_text)
        self.assertEqual(get_hint.call_count, 2)


if __name__ == "__main__":
    unittest.main()
