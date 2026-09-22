from datetime import datetime

from backend.schemas import HintEvent, HintStrength
from mcp_server.adapters.local_runtime import LocalRuntime

runtime = LocalRuntime()


def get_hint_history(session_id: str, puzzle_id: str) -> list[dict]:
    return [
        event.model_dump(mode="json")
        for event in runtime.get_hint_history(session_id, puzzle_id)
    ]


def get_approved_hint(theme_id: str, puzzle_id: str, strength: str) -> str:
    # STRONG도 승인 데이터만 조회한다. 강도 판단 자체는 LLM/도메인 평가 대상이며
    # ANSWER 정답 공개는 별도 AnswerVault/동의 경계를 유지한다.
    return runtime.get_approved_hint(theme_id, puzzle_id, strength)


def record_hint_delivery(
    session_id: str,
    team_id: str,
    puzzle_id: str,
    strength: str,
    delivered_at: str,
    reason_codes: list[str],
    idempotency_key: str | None = None,
) -> dict:
    event = HintEvent(
        session_id=session_id,
        team_id=team_id,
        puzzle_id=puzzle_id,
        strength=HintStrength(strength),
        delivered_at=datetime.fromisoformat(delivered_at),
        reason_codes=reason_codes,
        idempotency_key=idempotency_key,
    )
    return runtime.record_hint_delivery(event)
