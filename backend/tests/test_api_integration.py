import unittest

from backend.services.agent_orchestrator import mcp

try:
    from fastapi.testclient import TestClient
    from backend.main import app
except ModuleNotFoundError as exc:  # 개발 런타임에 FastAPI가 없을 때도 나머지 테스트는 실행
    TestClient = None
    app = None
    FASTAPI_IMPORT_ERROR = str(exc)
else:
    FASTAPI_IMPORT_ERROR = ""


@unittest.skipIf(TestClient is None, f"FastAPI dependency unavailable: {FASTAPI_IMPORT_ERROR}")
class AnswerApiIntegrationTests(unittest.TestCase):
    def test_openapi_exposes_answer_confirmation_contract(self):
        # 수정 사유: 프론트가 참고하는 OpenAPI 경로가 실제 라우터와 일치하는지 확인한다.
        client = TestClient(app)
        schema = client.get("/openapi.json").json()
        self.assertIn("/api/agent", schema["paths"])
        self.assertIn("/api/answers/confirm", schema["paths"])
        self.assertNotIn("/api/answers/reveal", schema["paths"])
        # 수정 기획안: QR 입장과 고객 직접 진도 변경은 P0 공개 API가 아니다.
        self.assertNotIn("/api/sessions/{session_id}/qr.svg", schema["paths"])
        self.assertNotIn("/api/sessions/{session_id}/solve", schema["paths"])
        self.assertEqual(
            schema["paths"]["/api/answers/confirm"]["post"]["responses"]["200"]["description"],
            "Successful Response",
        )

    def test_agent_to_answer_confirmation_api_flow(self):
        # 수정 사유: 실제 HTTP 계약에서 정답이 동의 전 노출되지 않는지 검증한다.
        session = mcp.create_session("last_train", "team-api-integration")
        client = TestClient(app)

        agent_response = client.post(
            "/api/agent",
            json={
                "session_id": session["session_id"],
                "team_id": "team-api-integration",
                "puzzle_id": session["current_puzzle_id"],
                "message": "정답 알려줘",
            },
        )
        self.assertEqual(agent_response.status_code, 200)
        agent_body = agent_response.json()
        self.assertEqual(agent_body["status"], "ANSWER_CONFIRMATION_REQUIRED")
        self.assertNotIn("DEMO_ANSWER", agent_response.text)

        confirm_response = client.post(
            "/api/answers/confirm",
            json={
                "session_id": session["session_id"],
                "team_id": "team-api-integration",
                "puzzle_id": session["current_puzzle_id"],
                "offer_id": agent_body["offer_id"],
            },
        )
        self.assertEqual(confirm_response.status_code, 200)
        self.assertEqual(confirm_response.json()["policy"], "USER_EXPLICIT_CONFIRMATION")

        reused_response = client.post(
            "/api/answers/confirm",
            json={
                "session_id": session["session_id"],
                "team_id": "team-api-integration",
                "puzzle_id": session["current_puzzle_id"],
                "offer_id": agent_body["offer_id"],
            },
        )
        self.assertEqual(reused_response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
