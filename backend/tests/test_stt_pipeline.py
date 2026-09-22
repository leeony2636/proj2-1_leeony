import pytest
from fastapi.testclient import TestClient

from backend.main import app
from backend.schemas import AgentResponse, AgentStatus, STTResult
from backend.services.mcp_client import MCPClient
from backend.services.stt import MockSTTAdapter, transcribe_then_handle


client = TestClient(app)


class GoodAdapter:
    def transcribe(self, request):
        return STTResult(
            transcript="이 퍼즐의 다음 단계를 알려주세요",
            confidence=0.92,
            language="ko-KR",
            duration_ms=2400,
            provider="test",
            model="test-stt",
            request_id="stt-test-1",
        )


def test_accepted_transcript_becomes_the_llm_message(monkeypatch):
    captured = {}

    def fake_agent(request):
        captured["message"] = request.message
        return AgentResponse(
            status=AgentStatus.NEED_MORE_INFO,
            session_id=request.session_id,
            team_id=request.team_id,
            puzzle_id=request.puzzle_id,
        )

    monkeypatch.setattr("backend.services.stt.handle_agent_request", fake_agent)

    result = transcribe_then_handle(
        GoodAdapter(),
        audio_bytes=b"audio",
        content_type="audio/webm",
        session_id="session-stt-1",
        team_id="team-stt-1",
        puzzle_id="train-p01",
    )

    assert result.status == "ACCEPTED"
    assert result.agent_response is not None
    assert captured["message"] == "이 퍼즐의 다음 단계를 알려주세요"


def test_low_confidence_stt_does_not_call_llm(monkeypatch):
    class LowConfidenceAdapter(GoodAdapter):
        def transcribe(self, request):
            return GoodAdapter.transcribe(self, request).model_copy(update={"confidence": 0.45})

    monkeypatch.setattr(
        "backend.services.stt.handle_agent_request",
        lambda _: pytest.fail("LLM must not be called for low-confidence STT"),
    )

    result = transcribe_then_handle(
        LowConfidenceAdapter(),
        audio_bytes=b"audio",
        content_type="audio/webm",
        session_id="session-stt-low",
        team_id="team-stt-low",
        puzzle_id="train-p01",
    )

    assert result.status == "RETRY_REQUIRED"
    assert result.reason_codes == ["STT_LOW_CONFIDENCE"]
    assert result.agent_response is None


def test_stt_timeout_does_not_call_llm(monkeypatch):
    class TimeoutAdapter:
        def transcribe(self, request):
            raise TimeoutError("provider timeout")

    monkeypatch.setattr(
        "backend.services.stt.handle_agent_request",
        lambda _: pytest.fail("LLM must not be called after STT timeout"),
    )

    result = transcribe_then_handle(
        TimeoutAdapter(),
        audio_bytes=b"audio",
        content_type="audio/webm",
        session_id="session-stt-timeout",
        team_id="team-stt-timeout",
        puzzle_id="train-p01",
    )

    assert result.status == "RETRY_REQUIRED"
    assert result.reason_codes == ["STT_PROVIDER_TIMEOUT"]


def test_mock_adapter_returns_transcript_without_selecting_a_model():
    result = MockSTTAdapter().transcribe(
        {
            "audio_bytes": "힌트 주세요".encode("utf-8"),
            "content_type": "audio/webm",
            "language": "ko-KR",
            "max_duration_ms": 15_000,
        }
    )

    assert result.transcript == "힌트 주세요"
    assert result.provider == "mock"
    assert result.model == "mock-stt"


def test_voice_endpoint_passes_mock_transcript_into_agent_flow():
    session = MCPClient().create_session("last_train", "team-stt-route")
    response = client.post(
        "/api/agent/voice",
        files={"audio": ("hint.webm", "힌트 주세요".encode("utf-8"), "audio/webm")},
        data={
            "session_id": session["session_id"],
            "team_id": "team-stt-route",
            "puzzle_id": session["current_puzzle_id"],
            "language": "ko-KR",
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ACCEPTED"
    assert response.json()["agent_response"]["hint_text"]
