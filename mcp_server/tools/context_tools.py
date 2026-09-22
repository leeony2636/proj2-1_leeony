from datetime import datetime, timezone

from backend.schemas import ConversationTurn
from mcp_server.adapters.local_runtime import LocalRuntime

runtime = LocalRuntime()


def get_conversation_history(session_id: str, limit: int = 6) -> list[dict]:
    return [turn.model_dump(mode="json") for turn in runtime.get_conversation_history(session_id, limit)]


def record_conversation_turn(
    session_id: str,
    role: str,
    content: str,
    request_id: str | None = None,
) -> dict:
    turn = ConversationTurn(
        role=role,
        content=content,
        created_at=datetime.now(timezone.utc),
        request_id=request_id,
    )
    runtime.record_conversation_turn(session_id, turn)
    return turn.model_dump(mode="json")
