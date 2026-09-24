import unittest

from backend.schemas import AgentRequest, AgentStatus
from backend.services.agent_orchestrator import handle_agent_request
from mcp_server.adapters.local_runtime import LocalRuntime


class StrongHintAutoDeliveryTests(unittest.TestCase):
    def test_strong_hint_is_delivered_automatically(self):
        runtime = LocalRuntime()
        session = runtime.create_session("professors_lab", "TEAM-AUTO-001")

        # 수정 사유: STRONG은 고객 동의 대기가 아니라 정책 충족 시 자동 제공으로 확정했다.
        response = handle_agent_request(
            AgentRequest(
                session_id=session.session_id,
                team_id=session.team_id,
                puzzle_id=session.current_puzzle_id,
                message="강한 힌트 주세요",
            )
        )

        self.assertIs(response.status, AgentStatus.PROVIDE_HINT)
        self.assertEqual(response.hint_strength.value, "STRONG")
        self.assertTrue(response.hint_text)
        self.assertFalse(response.requires_confirmation)
        self.assertIsNone(response.offer_id)
        self.assertFalse(hasattr(response, "answer_reveal_url"))
