"""Langfuse 관측 경계.

AgentResponse 전체를 trace에 전달하지 않고 허용 목록 DTO만 전송한다.
정답·승인 힌트·토큰·음성 전사문은 관측 데이터에서 제외한다.
"""

from __future__ import annotations

import hashlib
import os
from typing import Any

from pydantic import BaseModel, Field

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - requirements 설치 전에도 Agent는 동작해야 한다.
    Langfuse = None  # type: ignore[assignment,misc]


class ObservationEvent(BaseModel):
    event_name: str
    request_id: str | None = None
    session_id: str | None = None
    team_id_hash: str | None = None
    puzzle_id: str | None = None
    status: str | None = None
    intent: str | None = None
    emotion: str | None = None
    hint_strength: str | None = None
    reason_codes: list[str] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)
    decision_source: str | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    next_action: str | None = None
    stt_provider: str | None = None
    stt_model: str | None = None
    stt_confidence: float | None = None
    stt_status: str | None = None


_client: Any | None = None
_client_config: tuple[str, str, str] | None = None


def _hash_identifier(value: Any) -> str | None:
    if not value:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def build_observation(event_name: str, payload: dict) -> ObservationEvent:
    """응답 payload에서 관측 허용 필드만 추출한다."""
    return ObservationEvent(
        event_name=event_name,
        request_id=payload.get("request_id"),
        session_id=payload.get("session_id"),
        team_id_hash=_hash_identifier(payload.get("team_id")),
        puzzle_id=payload.get("puzzle_id"),
        status=payload.get("status"),
        intent=payload.get("intent"),
        emotion=payload.get("emotion"),
        hint_strength=payload.get("hint_strength"),
        reason_codes=list(payload.get("reason_codes") or []),
        selected_tools=list(payload.get("selected_tools") or []),
        decision_source=payload.get("decision_source"),
        llm_provider=payload.get("llm_provider"),
        llm_model=payload.get("llm_model"),
        next_action=payload.get("next_action"),
        stt_provider=payload.get("stt_provider"),
        stt_model=payload.get("stt_model"),
        stt_confidence=payload.get("stt_confidence"),
        stt_status=payload.get("stt_status"),
    )


def _get_client() -> Any | None:
    global _client, _client_config
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
    secret_key = os.getenv("LANGFUSE_SECRET_KEY", "").strip()
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com").strip()
    config = (public_key, secret_key, host)
    if _client_config == config:
        return _client
    _client_config = config
    _client = None

    if not public_key or not secret_key or Langfuse is None:
        return None

    try:
        _client = Langfuse(
            public_key=public_key,
            secret_key=secret_key,
            host=host,
        )
    except Exception:
        # 수정 사유: 관측 Provider 장애가 고객 힌트 제공을 막지 않도록 fail-open한다.
        _client = None
    return _client


def record_event(event_name: str, payload: dict) -> bool:
    """안전한 관측 이벤트만 Langfuse에 전송하고 전송 성공 여부를 반환한다."""
    observation = build_observation(event_name, payload)
    client = _get_client()
    if client is None:
        return False

    safe_payload = observation.model_dump(mode="json", exclude_none=True)
    try:
        with client.start_as_current_observation(
            name=f"agent.{event_name}",
            as_type="chain",
            output=safe_payload,
            metadata={"request_id": observation.request_id, "status": observation.status},
        ):
            pass
        if os.getenv("LANGFUSE_FLUSH_ON_EVENT", "true").lower() == "true":
            client.flush()
        return True
    except Exception:
        # 수정 사유: Langfuse 네트워크·SDK 오류는 핵심 Agent 흐름의 실패 상태가 아니다.
        return False
