"""LLM 판단의 단일 진입점.

프로덕션 경로에서는 자연어 + 최소 세션 맥락 + 버전이 있는 Domain Skill을 받아
복합 의도/필요 조회/추가 질문/행동 계획을 구조화한다. 읽기 전용 도구 결과가
필요한 경우에만 2차 판단을 수행한다. baseline은 비교 전용이며 자동 fallback이 아니다.
"""
from __future__ import annotations

import json
import os
import re
import time
from typing import Any

from backend.schemas import (
    AgentActionType,
    AgentContext,
    EmotionSignal,
    IntentResult,
    IntentType,
    LookupToolType,
    SupportNeed,
)
from backend.services.baseline_router import classify_intent_baseline
from backend.services.langfuse_service import record_event


PROMPT_VERSION = "agent-domain-v2.2"

SYSTEM_PROMPT = """당신은 방탈출 카페 운영 보조 Agent의 도메인 판단 모듈이다.
키워드 분류기가 아니라 현재 세션 맥락, 최근 대화, 버전이 명시된 Domain Skill,
그리고 필요한 경우 읽기 전용 도구 결과를 근거로 판단한다.

반드시 JSON 객체 하나만 반환한다.

필드:
- intent: HINT | EQUIPMENT_ISSUE | MASTER_REQUEST | TIME_EXTENSION_REQUEST | UNCLEAR
- intents: 위 intent 배열. 독립적인 복합 요청일 때만 여러 개
- actions: PROVIDE_HINT | REQUEST_GAME_MASTER | REPORT_EQUIPMENT | REQUEST_TIME_EXTENSION | ASK_CLARIFICATION 배열
- lookup_tools: get_hint_history | get_master_request_status 배열. 실제로 필요한 조회만 선택
- emotion: LOW | MEDIUM | HIGH
- needs_clarification: boolean
- clarifying_question: string | null
- reason: 현재 근거와 판단을 1~2문장으로 요약
- direct_answer_request: boolean
- strong_hint_request: boolean
- frustration_high: boolean
- support_need: STANDARD | STRONG | ANSWER
- customer_guidance: 확인된 조회 결과를 설명할 때 쓸 짧은 안내. 미확인 실행 완료를 주장하지 말 것
- staff_facts: 고객이 직접 말했거나 도구로 확인된 사실 배열
- staff_attempts: 고객이 이미 했다고 말한 시도 배열
- staff_unknowns: 아직 확인되지 않은 사항 배열
- applied_skill_rules: 이번 판단에 적용했다고 스스로 보고하는 domain_skill rule id 배열. 준수 증명이 아니라 평가용 자기보고 메타데이터다.
- context_notes: 실제 판단에 사용한 맥락 요약 배열

판단 원칙:
1) domain_skill.confirmed_boundaries는 반드시 지킨다.
2) domain_skill.llm_guidance는 판단 참고 기준으로 사용할 수 있지만, unconfirmed_policy_ids는 자동 규칙으로 적용하지 않는다.
3) domain_skill에서 visibility=INTERNAL_ONLY인 값과 메타데이터는 고객 안내에 직접 노출하지 않는다.
4) 승인되지 않은 힌트/정답을 만들지 않는다. 힌트 본문은 코드가 승인 데이터에서 조회한다.
5) '안 열린다/반응 없다'는 말만으로 장비 이상을 확정하지 않는다. 힌트 문제와 같은 원인인지 독립 요청인지 불명확하면 질문 또는 필요한 조회를 먼저 선택한다.
6) '아까/그거/아직'처럼 과거 처리 상태가 필요한 요청은 get_hint_history 또는 get_master_request_status를 선택할 수 있다.
7) 조회가 필요한 경우 부작용 action을 성급히 확정하지 말고 lookup_tools를 우선 반환한다. 조회 결과를 받은 FOLLOWUP 단계에서 최종 action을 판단한다.
8) 정보가 정말 부족하고 조회로 해결되지 않을 때만 ASK_CLARIFICATION을 사용하며 질문은 한 번에 하나만 한다.
9) 시간 연장은 자동 승인하지 않는다. 장비 원인/긴급도/우선순위를 근거 없이 확정하지 않는다.
10) 직원 전달 정보는 facts/attempts/unknowns를 섞지 않는다.
11) actions는 실제 실행 의도다. 단순 추천/장식 필드를 만들지 않는다.
"""


def _append_audit(audit: list[dict[str, Any]] | None, item: dict[str, Any]) -> None:
    if audit is not None:
        audit.append(item)


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.S)
        if not match:
            raise
        return json.loads(match.group(0))


def _enum_list(values: object, enum_type):
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        try:
            item = enum_type(value)
        except (TypeError, ValueError):
            continue
        if item not in result:
            result.append(item)
    return result


def _string_list(values: object, limit: int = 8, item_limit: int = 240) -> list[str]:
    if not isinstance(values, list):
        return []
    return [str(x)[:item_limit] for x in values if isinstance(x, (str, int, float))][:limit]


def _normalize(data: dict, provider: str, model: str, skill_version: str | None) -> IntentResult:
    try:
        primary = IntentType(data.get("intent", "UNCLEAR"))
    except ValueError:
        primary = IntentType.UNCLEAR
    intents = _enum_list(data.get("intents", []), IntentType) or [primary]
    actions = _enum_list(data.get("actions", []), AgentActionType)
    lookups = _enum_list(data.get("lookup_tools", []), LookupToolType)
    try:
        emotion = EmotionSignal(data.get("emotion", "LOW"))
    except ValueError:
        emotion = EmotionSignal.LOW
    try:
        support_need = SupportNeed(data.get("support_need", "STANDARD"))
    except ValueError:
        support_need = SupportNeed.STANDARD

    return IntentResult(
        intent=primary,
        intents=intents,
        actions=actions,
        lookup_tools=lookups,
        emotion=emotion,
        needs_clarification=bool(data.get("needs_clarification", False)),
        clarifying_question=(str(data["clarifying_question"])[:300] if data.get("clarifying_question") else None),
        reason=str(data.get("reason", "LLM_DECISION"))[:500],
        direct_answer_request=bool(data.get("direct_answer_request", False)),
        strong_hint_request=bool(data.get("strong_hint_request", False)),
        frustration_high=bool(data.get("frustration_high", False)),
        support_need=support_need,
        customer_guidance=(str(data["customer_guidance"])[:500] if data.get("customer_guidance") else None),
        staff_facts=_string_list(data.get("staff_facts")),
        staff_attempts=_string_list(data.get("staff_attempts")),
        staff_unknowns=_string_list(data.get("staff_unknowns")),
        applied_skill_rules=_string_list(data.get("applied_skill_rules"), item_limit=120),
        context_notes=_string_list(data.get("context_notes")),
        provider=provider,
        model=model,
        prompt_version=PROMPT_VERSION,
        skill_version=skill_version,
    )


def inspect_raw_contract(data: object) -> dict[str, Any]:
    """정규화 전 모델 JSON이 계약을 지켰는지 기술적으로만 검사한다."""
    if not isinstance(data, dict):
        return {"raw_contract_valid": False, "raw_contract_errors": ["ROOT_NOT_OBJECT"]}

    errors: list[str] = []
    enum_fields = {
        "intent": {x.value for x in IntentType},
        "emotion": {x.value for x in EmotionSignal},
        "support_need": {x.value for x in SupportNeed},
    }
    list_enum_fields = {
        "intents": {x.value for x in IntentType},
        "actions": {x.value for x in AgentActionType},
        "lookup_tools": {x.value for x in LookupToolType},
    }
    for field, allowed in enum_fields.items():
        if field not in data:
            errors.append(f"MISSING:{field}")
        elif data[field] not in allowed:
            errors.append(f"INVALID_ENUM:{field}")
    for field, allowed in list_enum_fields.items():
        value = data.get(field)
        if not isinstance(value, list):
            errors.append(f"NOT_LIST:{field}")
        elif any(item not in allowed for item in value):
            errors.append(f"INVALID_LIST_ENUM:{field}")

    for field in ("needs_clarification", "direct_answer_request", "strong_hint_request", "frustration_high"):
        if field not in data:
            errors.append(f"MISSING:{field}")
        elif not isinstance(data[field], bool):
            errors.append(f"NOT_BOOL:{field}")

    for field in ("staff_facts", "staff_attempts", "staff_unknowns", "applied_skill_rules", "context_notes"):
        value = data.get(field)
        if not isinstance(value, list):
            errors.append(f"NOT_LIST:{field}")
        elif any(not isinstance(item, str) for item in value):
            errors.append(f"NON_STRING_ITEM:{field}")

    if "reason" not in data or not isinstance(data.get("reason"), str):
        errors.append("MISSING_OR_NON_STRING:reason")
    clarification = data.get("clarifying_question")
    if clarification is not None and not isinstance(clarification, str):
        errors.append("INVALID_TYPE:clarifying_question")
    guidance = data.get("customer_guidance")
    if guidance is not None and not isinstance(guidance, str):
        errors.append("INVALID_TYPE:customer_guidance")

    return {"raw_contract_valid": not errors, "raw_contract_errors": errors}


def normalization_changes(data: dict, normalized: IntentResult) -> list[str]:
    """원래 모델 JSON과 정규화 결과가 달라진 계약 필드를 기록한다."""
    actual = normalized.model_dump(mode="json")
    fields = [
        "intent",
        "intents",
        "actions",
        "lookup_tools",
        "emotion",
        "needs_clarification",
        "support_need",
        "direct_answer_request",
        "strong_hint_request",
        "frustration_high",
        "staff_facts",
        "staff_attempts",
        "staff_unknowns",
        "applied_skill_rules",
        "context_notes",
    ]
    return [field for field in fields if data.get(field) != actual.get(field)]


def _usage_value(usage, name: str):
    if usage is None:
        return None
    if isinstance(usage, dict):
        return usage.get(name)
    return getattr(usage, name, None)


def _openrouter_decision(
    *,
    stage: str,
    payload: dict,
    skill_version: str | None,
    request_id: str | None = None,
    session_id: str | None = None,
    audit: list[dict[str, Any]] | None = None,
) -> IntentResult:
    from openai import OpenAI

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY_MISSING")

    model = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    user_payload = {"stage": stage, **payload}
    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": json.dumps(user_payload, ensure_ascii=False)},
        ],
        temperature=0,
        max_tokens=850,
    )

    headers = {}
    if os.getenv("OPENROUTER_SITE_URL"):
        headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL")
    if os.getenv("OPENROUTER_APP_NAME"):
        headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME")
    if headers:
        kwargs["extra_headers"] = headers

    retry_count = 0
    started = time.perf_counter()
    try:
        try:
            response = client.chat.completions.create(
                **kwargs,
                response_format={"type": "json_object"},
            )
        except Exception as first_exc:
            retry_count = 1
            record_event(
                "llm_retry",
                {
                    "trace_id": request_id,
                    "request_id": request_id,
                    "session_id": session_id,
                    "llm_provider": "openrouter",
                    "llm_model": model,
                    "prompt_version": PROMPT_VERSION,
                    "skill_version": skill_version,
                    "llm_stage": stage,
                    "retry_count": retry_count,
                    "error_type": type(first_exc).__name__,
                },
            )
            _append_audit(
                audit,
                {
                    "stage": "LLM_RETRY",
                    "llm_stage": stage,
                    "retry_count": retry_count,
                    "error_type": type(first_exc).__name__,
                },
            )
            # JSON mode 미지원 모델을 위한 형식 fallback이며 의미 판단을 baseline으로 대체하지 않는다.
            response = client.chat.completions.create(**kwargs)
    except Exception as exc:
        record_event(
            "llm_call_failed",
            {
                "trace_id": request_id,
                "request_id": request_id,
                "session_id": session_id,
                "llm_provider": "openrouter",
                "llm_model": model,
                "prompt_version": PROMPT_VERSION,
                "skill_version": skill_version,
                "llm_stage": stage,
                "retry_count": retry_count,
                "error_type": type(exc).__name__,
            },
        )
        raise
    finally:
        latency_ms = round((time.perf_counter() - started) * 1000, 2)

    usage = getattr(response, "usage", None)
    cost = _usage_value(usage, "cost")
    record_event(
        "llm_call",
        {
            "trace_id": request_id,
            "request_id": request_id,
            "session_id": session_id,
            "llm_provider": "openrouter",
            "llm_model": model,
            "prompt_version": PROMPT_VERSION,
            "skill_version": skill_version,
            "llm_stage": stage,
            "latency_ms": latency_ms,
            "input_tokens": _usage_value(usage, "prompt_tokens"),
            "output_tokens": _usage_value(usage, "completion_tokens"),
            "total_tokens": _usage_value(usage, "total_tokens"),
            # Provider가 cost를 제공할 때만 기록한다. 미제공은 None이며 0으로 바꾸지 않는다.
            "cost_usd": cost,
            "cost_source": "PROVIDER_REPORTED" if cost is not None else "NOT_PROVIDED",
            "retry_count": retry_count,
        },
    )

    content = response.choices[0].message.content or "{}"
    raw = _extract_json(content)
    contract = inspect_raw_contract(raw)
    normalized = _normalize(raw, "openrouter", model, skill_version)
    changed = normalization_changes(raw, normalized)
    _append_audit(
        audit,
        {
            "stage": "LLM_CONTRACT",
            "llm_stage": stage,
            **contract,
            "normalization_changed_fields": changed,
            "normalized_contract_valid": True,
            "provider": "openrouter",
            "model": model,
            "prompt_version": PROMPT_VERSION,
            "skill_version": skill_version,
            "retry_count": retry_count,
        },
    )
    return normalized


def _baseline(message: str, context: AgentContext) -> IntentResult:
    """비교 실험/오프라인 테스트용 키워드 baseline."""
    result = classify_intent_baseline(message)
    result.intents = [result.intent]
    result.lookup_tools = []
    if result.intent == IntentType.EQUIPMENT_ISSUE:
        result.actions = [AgentActionType.REPORT_EQUIPMENT]
    elif result.intent == IntentType.MASTER_REQUEST:
        result.actions = [AgentActionType.REQUEST_GAME_MASTER]
    elif result.intent == IntentType.TIME_EXTENSION_REQUEST:
        result.actions = [AgentActionType.REQUEST_TIME_EXTENSION]
    elif result.intent == IntentType.HINT:
        result.actions = [AgentActionType.PROVIDE_HINT]
    else:
        result.actions = [AgentActionType.ASK_CLARIFICATION]
        result.clarifying_question = "어떤 도움이 필요한지 조금 더 구체적으로 말씀해 주세요."

    if result.direct_answer_request:
        result.support_need = SupportNeed.ANSWER
    elif result.strong_hint_request or result.frustration_high:
        result.support_need = SupportNeed.STRONG
    else:
        result.support_need = SupportNeed.STANDARD
    result.context_notes = ["baseline은 Domain Skill/세션 맥락을 의미 판단에 사용하지 않음"]
    result.provider = "baseline"
    result.model = "keyword-baseline"
    result.prompt_version = "baseline-v1"
    result.skill_version = None
    return result


def analyze_user_request(
    message: str,
    context: AgentContext,
    provider: str | None = None,
    *,
    request_id: str | None = None,
    audit: list[dict[str, Any]] | None = None,
) -> IntentResult:
    selected = (provider or os.getenv("LLM_PROVIDER", "")).strip().lower()
    if not selected:
        raise RuntimeError("LLM_PROVIDER_REQUIRED")
    if selected == "baseline":
        return _baseline(message, context)
    if selected == "openrouter":
        return _openrouter_decision(
            stage="INITIAL",
            payload={"message": message, "context": context.model_dump(mode="json")},
            skill_version=context.domain_skill.get("version"),
            request_id=request_id,
            session_id=context.session_id,
            audit=audit,
        )
    raise ValueError(f"UNSUPPORTED_LLM_PROVIDER:{selected}")


def analyze_after_tools(
    message: str,
    context: AgentContext,
    previous: IntentResult,
    provider: str | None = None,
    *,
    request_id: str | None = None,
    audit: list[dict[str, Any]] | None = None,
) -> IntentResult:
    """선택한 읽기 전용 도구 결과를 근거로 최종 행동을 다시 판단한다."""
    selected = (provider or os.getenv("LLM_PROVIDER", "")).strip().lower()
    if not selected:
        raise RuntimeError("LLM_PROVIDER_REQUIRED")
    if selected == "baseline":
        # baseline은 도구 후속 판단 품질 비교 대상이 아니므로 새 의미 판단을 꾸미지 않는다.
        previous.lookup_tools = []
        return previous
    if selected == "openrouter":
        return _openrouter_decision(
            stage="FOLLOWUP_AFTER_TOOLS",
            payload={
                "message": message,
                "context": context.model_dump(mode="json"),
                "previous_decision": previous.model_dump(mode="json"),
                "instruction": "tool_results를 근거로 최종 actions/질문/customer_guidance를 다시 결정하라. lookup_tools는 빈 배열로 끝낸다.",
            },
            skill_version=context.domain_skill.get("version"),
            request_id=request_id,
            session_id=context.session_id,
            audit=audit,
        )
    raise ValueError(f"UNSUPPORTED_LLM_PROVIDER:{selected}")
