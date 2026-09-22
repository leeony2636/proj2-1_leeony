from fastapi import APIRouter, File, Form, UploadFile

from backend.schemas import STTAgentResponse
from backend.services.stt import MockSTTAdapter, transcribe_then_handle


router = APIRouter(prefix="/api", tags=["stt"])
adapter = MockSTTAdapter()


@router.post("/agent/voice", response_model=STTAgentResponse)
async def voice_agent(
    audio: UploadFile = File(...),
    session_id: str = Form(...),
    team_id: str = Form(...),
    puzzle_id: str | None = Form(default=None),
    language: str = Form(default="ko-KR"),
) -> STTAgentResponse:
    audio_bytes = await audio.read()
    return transcribe_then_handle(
        adapter,
        audio_bytes=audio_bytes,
        content_type=audio.content_type or "",
        session_id=session_id,
        team_id=team_id,
        puzzle_id=puzzle_id,
        language=language,
    )
