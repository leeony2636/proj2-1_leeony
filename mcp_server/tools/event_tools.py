from __future__ import annotations

from datetime import datetime

from backend.schemas import GameEventType
from mcp_server.adapters.local_runtime import LocalRuntime


runtime = LocalRuntime()


def get_game_events(session_id: str, limit: int = 50) -> list[dict]:
    return [
        event.model_dump(mode="json")
        for event in runtime.get_game_events(session_id, limit=limit)
    ]


def record_game_event(
    session_id: str,
    team_id: str,
    event_type: str,
    puzzle_id: str | None = None,
    payload: dict | None = None,
    occurred_at: str | None = None,
) -> dict:
    event = runtime.record_game_event(
        session_id=session_id,
        team_id=team_id,
        event_type=GameEventType(event_type),
        puzzle_id=puzzle_id,
        payload=payload,
        occurred_at=(datetime.fromisoformat(occurred_at) if occurred_at else None),
    )
    return event.model_dump(mode="json")
