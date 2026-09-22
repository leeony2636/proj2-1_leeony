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
    # STRONG은 동의 대기 단계가 아니라 코드 정책 충족 시 자동 전달한다.
    # ANSWER 동의/offer 흐름은 별도 승인 콘텐츠 계약을 확정한 뒤 추가한다.
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
