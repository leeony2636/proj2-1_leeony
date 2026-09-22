"""음성 입력을 기존 텍스트 Agent 계약으로 연결하는 STT 경계."""

from __future__ import annotations

from typing import Protocol

from backend.schemas import (
    AgentRequest,
    STTAgentResponse,
    STTRequest,
    STTResult,
)
from backend.services.agent_orchestrator import handle_agent_request


SUPPORTED_CONTENT_TYPES = {"audio/webm", "audio/wav", "audio/mpeg", "audio/ogg"}
ACCEPT_CONFIDENCE = 0.80
RETRY_CONFIDENCE = 0.60


class STTAdapter(Protocol):
    def transcribe(self, request: STTRequest) -> STTResult:
        """Provider별 구현이 공통 STTResult를 반환한다."""


class MockSTTAdapter:
    """Provider 선정 전 계약과 파이프라인을 검증하기 위한 임시 Adapter."""

    def transcribe(self, request: STTRequest | dict) -> STTResult:
        request = STTRequest.model_validate(request)
        if request.content_type not in SUPPORTED_CONTENT_TYPES:
            raise ValueError("STT_UNSUPPORTED_AUDIO_FORMAT")

        # 수정 사유: 실제 모델을 확정하지 않은 P0에서는 UTF-8 테스트 음성을
        # 전사문으로 취급해 후속 Provider를 교체할 수 있는 계약만 검증한다.
        transcript = request.audio_bytes.decode("utf-8", errors="ignore").strip()
        return STTResult(
            transcript=transcript,
            confidence=0.99 if transcript else 0.0,
            language=request.language,
            duration_ms=1000,
            provider="mock",
            model="mock-stt",
        )


def _validate_result(result: STTResult, max_duration_ms: int) -> tuple[str, str]:
    if result.duration_ms > max_duration_ms:
        return "RETRY_REQUIRED", "STT_AUDIO_TOO_LONG"
    if not result.transcript.strip():
        return "RETRY_REQUIRED", "STT_EMPTY_TRANSCRIPT"
    if result.confidence < RETRY_CONFIDENCE:
        return "RETRY_REQUIRED", "STT_LOW_CONFIDENCE"
    if result.confidence < ACCEPT_CONFIDENCE:
        return "CONFIRMATION_REQUIRED", "STT_TRANSCRIPT_CONFIRMATION_REQUIRED"
    return "ACCEPTED", "STT_ACCEPTED"


def transcribe_then_handle(
    adapter: STTAdapter,
    *,
    audio_bytes: bytes,
    content_type: str,
    session_id: str,
    team_id: str,
    puzzle_id: str | None,
    language: str = "ko-KR",
    max_duration_ms: int = 15_000,
) -> STTAgentResponse:
    """전사 품질을 통과한 경우에만 기존 LLM/Agent 흐름을 호출한다."""
    request = STTRequest(
        audio_bytes=audio_bytes,
        content_type=content_type,
        language=language,
        max_duration_ms=max_duration_ms,
    )
    try:
        result = adapter.transcribe(request)
    except TimeoutError:
        return STTAgentResponse(status="RETRY_REQUIRED", reason_codes=["STT_PROVIDER_TIMEOUT"])
    except ValueError as exc:
        return STTAgentResponse(status="RETRY_REQUIRED", reason_codes=[str(exc)])

    status, reason = _validate_result(result, max_duration_ms)
    if status != "ACCEPTED":
        return STTAgentResponse(
            status=status,
            transcript=result.transcript,
            confidence=result.confidence,
            reason_codes=[reason],
            stt_request_id=result.request_id,
        )

    agent_response = handle_agent_request(
        AgentRequest(
            session_id=session_id,
            team_id=team_id,
            puzzle_id=puzzle_id,
            message=result.transcript.strip(),
        )
    )
    return STTAgentResponse(
        status="ACCEPTED",
        transcript=result.transcript.strip(),
        confidence=result.confidence,
        reason_codes=[reason],
        stt_request_id=result.request_id,
        agent_response=agent_response,
    )
