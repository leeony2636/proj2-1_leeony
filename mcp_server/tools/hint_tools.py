from datetime import datetime

from backend.schemas import HintEvent, HintStrength
from mcp_server.adapters.local_runtime import LocalRuntime

runtime = LocalRuntime()


def get_hint_history(session_id: str, puzzle_id: str) -> list[dict]:
    return [
        e.model_dump(mode="json")
        for e in runtime.get_hint_history(session_id, puzzle_id)
    ]


def get_approved_hint(theme_id: str, puzzle_id: str, strength: str) -> str:
    return runtime.get_approved_hint(theme_id, puzzle_id, strength)


def record_hint_delivery(
    session_id: str,
    team_id: str,
    puzzle_id: str,
    strength: str,
    delivered_at: str,
    reason_codes: list[str],
) -> dict:
    event = HintEvent(
        session_id=session_id,
        team_id=team_id,
        puzzle_id=puzzle_id,
        strength=HintStrength(strength),
        delivered_at=datetime.fromisoformat(delivered_at),
        reason_codes=reason_codes,
    )
    runtime.record_hint_delivery(event)
    return {"ok": True}
