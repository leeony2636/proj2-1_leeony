def record_event(event_name: str, payload: dict) -> None:
    """Langfuse 연결 전 trace 자리.

    실제 연결 시 기록 후보:
    request_id, user_id, session_id, puzzle_id,
    provider/model, prompt version, token/cost,
    LLM/MCP/total latency, retry/fallback.
    """
    _ = (event_name, payload)
