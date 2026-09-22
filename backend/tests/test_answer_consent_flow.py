from datetime import datetime, timezone
import unittest

from backend.schemas import AgentRequest, AgentStatus
from backend.services.agent_orchestrator import handle_agent_request, mcp
from backend.services.answer_vault import confirm_answer
from backend.services.answer_policy import should_auto_deliver_answer


class AnswerConsentFlowTests(unittest.TestCase):
    def test_direct_answer_request_returns_consent_offer_without_answer(self):
        # 수정 사유: 정답은 STRONG 자동 제공과 분리하고, 고객 동의 뒤에만 공개해야 한다.
        session = mcp.create_session("last_train", "team-answer-consent")
        response = handle_agent_request(
            AgentRequest(
                session_id=session["session_id"],
                team_id="team-answer-consent",
                puzzle_id=session["current_puzzle_id"],
                message="정답 알려줘",
            )
        )

        self.assertEqual(response.status, AgentStatus.ANSWER_CONFIRMATION_REQUIRED)
        self.assertEqual(response.hint_strength.value, "STRONG")
        self.assertTrue(response.requires_confirmation)
        self.assertIsNotNone(response.offer_id)
        self.assertNotIn("DEMO_ANSWER", response.model_dump_json())

        revealed = confirm_answer(
            session["session_id"],
            "team-answer-consent",
            session["current_puzzle_id"],
            response.offer_id,
        )
        self.assertEqual(revealed["policy"], "USER_EXPLICIT_CONFIRMATION")
        self.assertTrue(revealed["answer"])

    def test_answer_offer_cannot_be_confirmed_with_unknown_token(self):
        session = mcp.create_session("last_train", "team-answer-invalid")
        with self.assertRaises(PermissionError):
            confirm_answer(
                session["session_id"],
                "team-answer-invalid",
                session["current_puzzle_id"],
                "answer-offer-does-not-exist",
            )

    def test_answer_auto_delivery_is_disabled_even_when_time_is_short(self):
        session = mcp.create_session("last_train", "team-answer-auto-disabled")
        self.assertFalse(should_auto_deliver_answer(session, 1.0))


if __name__ == "__main__":
    unittest.main()
