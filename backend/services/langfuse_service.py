"""Langfuse 관측 경계.

AgentResponse 전체를 trace에 전달하지 않고 허용 목록 DTO만 전송한다.
정답·승인 힌트·토큰·음성 전사문은 관측 데이터에서 제외한다.
"""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

try:
    from langfuse import Langfuse
except ImportError:  # pragma: no cover - requirements 설치 전에도 Agent는 동작해야 한다.
    Langfuse = None  # type: ignore[assignment,misc]


class ObservationEvent(BaseModel):
    event_name: str
    trace_id: str | None = None
    langfuse_trace_id: str | None = None
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
    prompt_version: str | None = None
    skill_version: str | None = None
    llm_stage: str | None = None
    latency_ms: float | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    reasoning_tokens: int | None = None
    cached_tokens: int | None = None
    cache_write_tokens: int | None = None
    prompt_profile: dict[str, Any] | None = None
    call_strategy: str | None = None
    zdr_required: bool | None = None
    data_collection: str | None = None
    cost_usd: float | None = None
    cost_source: str | None = None
    retry_count: int | None = None
    error_type: str | None = None
    tool_name: str | None = None
    tool_status: str | None = None
    evaluation_name: str | None = None
    evaluation_score: float | None = None
    evaluation_run_id: str | None = None
    selection_run_id: str | None = None
    evaluation_case_id: str | None = None
    dataset_sha256: str | None = None
    quality_contract_sha256: str | None = None
    quality_status: str | None = None
    next_action: str | None = None
    stt_provider: str | None = None
    stt_model: str | None = None
    stt_confidence: float | None = None
    stt_status: str | None = None


_client: Any | None = None
_client_config: tuple[str, str, str] | None = None

EVALUATION_SCORE_NAMES = frozenset({
    "instruction_adherence", "context_understanding", "domain_judgment",
    "tool_judgment", "observation_interpretation", "structured_output_stability",
    "decision_consistency", "core30_auto_contract", "hard_fail_auto_guard",
})


def trace_id_for_seed(seed: str) -> str:
    """A valid, stable 32-hex Langfuse trace ID for one model run and case."""
    if not seed or not seed.strip():
        raise ValueError("TRACE_SEED_REQUIRED")
    return hashlib.sha256(f"escape-agent-eval:v1:{seed}".encode("utf-8")).hexdigest()[:32]


def _hash_identifier(value: Any) -> str | None:
    if not value:
        return None
    return hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:16]


def _safe_prompt_profile(value: Any) -> dict[str, Any] | None:
    """Keep only measured lengths/counts; never forward a nested prompt payload."""
    if not isinstance(value, dict):
        return None
    allowed_components = {
        "system_prompt", "user_message", "context_base", "domain_skill", "recent_turns",
        "tool_results", "previous_decision", "instruction", "other_payload",
        "repair_system_prompt", "repair_original_request", "repair_invalid_output",
        "repair_validation_failure",
    }
    safe: dict[str, Any] = {}
    for field in ("component_chars", "component_tokens_estimated"):
        components = value.get(field)
        if isinstance(components, dict):
            safe[field] = {
                name: number for name, number in components.items()
                if name in allowed_components and (number is None or type(number) is int)
            }
    if type(value.get("provider_input_tokens_actual")) is int:
        safe["provider_input_tokens_actual"] = value["provider_input_tokens_actual"]
    return safe


def build_observation(event_name: str, payload: dict) -> ObservationEvent:
    """응답 payload에서 관측 허용 필드만 추출한다."""
    return ObservationEvent(
        event_name=event_name,
        trace_id=payload.get("trace_id") or payload.get("request_id"),
        langfuse_trace_id=(
            trace_id_for_seed(str(payload.get("trace_id") or payload.get("request_id")))
            if payload.get("trace_id") or payload.get("request_id") else None
        ),
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
        prompt_version=payload.get("prompt_version"),
        skill_version=payload.get("skill_version"),
        llm_stage=payload.get("llm_stage"),
        latency_ms=payload.get("latency_ms"),
        input_tokens=payload.get("input_tokens"),
        output_tokens=payload.get("output_tokens"),
        total_tokens=payload.get("total_tokens"),
        reasoning_tokens=payload.get("reasoning_tokens"),
        cached_tokens=payload.get("cached_tokens"),
        cache_write_tokens=payload.get("cache_write_tokens"),
        prompt_profile=_safe_prompt_profile(payload.get("prompt_profile")),
        call_strategy=payload.get("call_strategy") or payload.get("strategy"),
        zdr_required=payload.get("zdr_required"),
        data_collection=payload.get("data_collection"),
        cost_usd=payload.get("cost_usd"),
        cost_source=payload.get("cost_source"),
        retry_count=payload.get("retry_count"),
        error_type=payload.get("error_type"),
        tool_name=payload.get("tool_name"),
        tool_status=payload.get("tool_status"),
        evaluation_name=payload.get("evaluation_name"),
        evaluation_score=payload.get("evaluation_score"),
        evaluation_run_id=payload.get("evaluation_run_id"),
        selection_run_id=payload.get("selection_run_id"),
        evaluation_case_id=str(payload["evaluation_case_id"]) if payload.get("evaluation_case_id") is not None else None,
        dataset_sha256=payload.get("dataset_sha256"),
        quality_contract_sha256=payload.get("quality_contract_sha256"),
        quality_status=payload.get("quality_status"),
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
    host = os.getenv("LANGFUSE_HOST", "").strip() or "https://cloud.langfuse.com"
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


def observability_configured() -> bool:
    """공식 평가 전 로컬 설정 존재 여부만 확인한다. 네트워크 성공을 보장하지 않는다."""
    return bool(
        os.getenv("LANGFUSE_PUBLIC_KEY", "").strip()
        and os.getenv("LANGFUSE_SECRET_KEY", "").strip()
        and Langfuse is not None
    )


def observability_auth_check() -> bool:
    """Make one authenticated, read-only Langfuse request before paid evaluation."""
    client = _get_client()
    if client is None:
        return False
    try:
        return client.auth_check() is True
    except Exception:
        return False


def record_event(event_name: str, payload: dict) -> bool:
    """안전한 관측 이벤트만 Langfuse에 전송하고 전송 성공 여부를 반환한다."""
    observation = build_observation(event_name, payload)
    client = _get_client()
    if client is None:
        return False

    safe_payload = observation.model_dump(mode="json", exclude_none=True)
    try:
        observation_type = "generation" if event_name == "llm_call" else ("tool" if event_name == "tool_call" else "chain")
        with client.start_as_current_observation(
            name=f"agent.{event_name}",
            as_type=observation_type,
            **({"trace_context": {"trace_id": observation.langfuse_trace_id}} if observation.langfuse_trace_id else {}),
            output=safe_payload,
            metadata={
                "trace_id": observation.langfuse_trace_id,
                "request_id": observation.request_id,
                "session_id": observation.session_id,
                "status": observation.status,
                "evaluation_run_id": observation.evaluation_run_id,
                "selection_run_id": observation.selection_run_id,
                "evaluation_case_id": observation.evaluation_case_id,
                "dataset_sha256": observation.dataset_sha256,
                "quality_contract_sha256": observation.quality_contract_sha256,
                "quality_status": observation.quality_status,
                "model": observation.llm_model,
                "prompt_version": observation.prompt_version,
                "skill_version": observation.skill_version,
            },
        ):
            pass
        if os.getenv("LANGFUSE_FLUSH_ON_EVENT", "true").lower() == "true":
            client.flush()
        return True
    except Exception:
        # 수정 사유: Langfuse 네트워크·SDK 오류는 핵심 Agent 흐름의 실패 상태가 아니다.
        return False


def record_evaluation_score(
    *,
    trace_seed: str,
    name: str,
    value: float,
    evaluation_started_at: str,
    evaluation_run_id: str,
    case_id: int,
    dataset_sha256: str,
    model: str,
) -> bool:
    """Write an idempotent native numeric Score to the matching safe case trace."""
    if name not in EVALUATION_SCORE_NAMES or value not in {0.0, 0.5, 1.0}:
        raise ValueError("INVALID_EVALUATION_SCORE")
    client = _get_client()
    if client is None:
        return False
    trace_id = trace_id_for_seed(trace_seed)
    score_id = hashlib.sha256(f"{trace_id}:{name}".encode("utf-8")).hexdigest()[:32]
    try:
        timestamp = datetime.fromisoformat(evaluation_started_at.replace("Z", "+00:00"))
        client.create_score(
            name=name,
            value=float(value),
            trace_id=trace_id,
            score_id=score_id,
            timestamp=timestamp,
            data_type="NUMERIC",
            metadata={
                "evaluation_run_id": evaluation_run_id,
                "case_id": case_id,
                "dataset_sha256": dataset_sha256,
                "model": model,
            },
        )
        client.flush()
        return True
    except Exception:
        return False
