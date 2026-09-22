import unittest
from datetime import datetime, timezone

from backend.schemas import (
    AgentResponse,
    AgentStatus,
    AnswerConfirmationRequest,
    AnswerResponse,
    HintStrength,
    IntentType,
)


class ApiContractTests(unittest.TestCase):
    def test_answer_confirmation_required_response_has_no_answer_field(self):
        # 수정 사유: Agent 성공 응답과 AnswerVault 공개 응답을 계약 수준에서 분리한다.
        response = AgentResponse(
            status=AgentStatus.ANSWER_CONFIRMATION_REQUIRED,
            session_id="session-contract",
            team_id="team-contract",
            puzzle_id="train-p01",
            intent=IntentType.HINT,
            hint_strength=HintStrength.STRONG,
            hint_text="강한 힌트",
            offer_id="aof_contract",
            offer_expires_at=datetime.now(timezone.utc),
            requires_confirmation=True,
        )
        payload = response.model_dump(mode="json")
        self.assertEqual(payload["status"], "ANSWER_CONFIRMATION_REQUIRED")
        self.assertTrue(payload["requires_confirmation"])
        self.assertNotIn("answer", payload)

    def test_confirmation_request_requires_scope_and_offer(self):
        request = AnswerConfirmationRequest(
            session_id="session-contract",
            team_id="team-contract",
            puzzle_id="train-p01",
            offer_id="aof_contract",
        )
        self.assertEqual(request.puzzle_id, "train-p01")

    def test_answer_response_has_explicit_confirmation_policy(self):
        response = AnswerResponse(
            puzzle_id="train-p01",
            answer="DEMO_ANSWER_01",
            policy="USER_EXPLICIT_CONFIRMATION",
        )
        self.assertEqual(response.policy, "USER_EXPLICIT_CONFIRMATION")


if __name__ == "__main__":
    unittest.main()
