import unittest

from backend.schemas import AgentRequest, AgentStatus
from backend.services.agent_orchestrator import handle_agent_request
from mcp_server.adapters.local_runtime import LocalRuntime


class StrongHintAutoDeliveryTests(unittest.TestCase):
    def test_strong_hint_is_delivered_automatically(self):
        runtime = LocalRuntime()
        session = runtime.create_session("professors_lab", "TEAM-AUTO-001")

        # STRONG support_need는 승인된 STRONG 힌트 데이터로 매핑되며 정답 공개와는 분리된다.
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
