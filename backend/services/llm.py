"""LLM 호출의 단일 진입점.

현재 실행 가능한 Provider
- baseline: API 키 없이 로컬 규칙 분류 (P0 기본값)
- openrouter: OpenRouter OpenAI-compatible API
- Azure OpenAI: 확정된 1순위 후보이며 실제 연결은 후속 작업

역할 분리
- LLM: 자연어 의도/감정/요청 성격 구조화 + MCP Tool 후보 선택
- 코드: WEAK/STRONG 최종 결정
- MCP: 실제 세션/퍼즐/힌트/이력 조회 및 기록
"""
from __future__ import annotations

import json
import os
import re

from backend.schemas import EmotionSignal, IntentResult, IntentType
from backend.services.intent_router import classify_intent_baseline


ALLOWED_TOOLS = {
    "get_game_session",
    "get_puzzle_context",
    "get_hint_history",
    "get_approved_hint",
    "record_hint_delivery",
    "request_game_master",
    "report_equipment_issue",
}

SYSTEM_PROMPT = """당신은 방탈출 고객 요청을 구조화하는 라우팅 Agent다.
당신은 힌트 강도를 최종 결정하지 않는다. 정답도 생성하지 않는다.
사용자 문장을 보고 아래 필드만 구조화한다.

intent: HINT | EQUIPMENT_ISSUE | MASTER_REQUEST | UNCLEAR
emotion: LOW | MEDIUM | HIGH
needs_clarification: boolean
reason: string
recommended_tools: string[]
direct_answer_request: boolean
strong_hint_request: boolean
frustration_high: boolean

사용 가능한 MCP Tool:
- get_game_session: 현재 세션/남은시간/진도 조회
- get_puzzle_context: 현재 퍼즐 정보 조회
- get_hint_history: 같은 퍼즐의 이전 힌트 이력 조회
- request_game_master: 사용자가 직원을 직접 요청했을 때
- report_equipment_issue: 소품/장비 이상일 때

규칙:
1) 소품/장비 고장·이상 => EQUIPMENT_ISSUE, tools=[report_equipment_issue]
2) 직원/게임마스터 직접 호출 => MASTER_REQUEST, tools=[request_game_master]
3) 일반 힌트/정답/강한 힌트 요청 => HINT
4) 정답을 직접 요구하면 direct_answer_request=true
5) 강한 힌트를 직접 요구하면 strong_hint_request=true
6) 시간 부족/반복 시도와 포기·무력감이 함께 명확하면 frustration_high=true, emotion=HIGH
7) 힌트 의도인데 puzzle_id가 없으면 needs_clarification=true
8) WEAK/STRONG은 절대 최종 결정하지 말 것
9) 출력은 JSON 한 개만 반환
"""


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


def _normalize(data: dict, provider: str, model: str) -> IntentResult:
    tools = [t for t in data.get("recommended_tools", []) if t in ALLOWED_TOOLS]
    return IntentResult(
        intent=IntentType(data.get("intent", "UNCLEAR")),
        emotion=EmotionSignal(data.get("emotion", "LOW")),
        needs_clarification=bool(data.get("needs_clarification", False)),
        reason=str(data.get("reason", "LLM_CLASSIFIED"))[:200],
        recommended_tools=tools,
        direct_answer_request=bool(data.get("direct_answer_request", False)),
        strong_hint_request=bool(data.get("strong_hint_request", False)),
        frustration_high=bool(data.get("frustration_high", False)),
        provider=provider,
        model=model,
    )


def _openrouter(message: str, puzzle_id: str | None) -> IntentResult:
    # baseline 모드에서는 openai 패키지가 없어도 실행되도록 지연 import한다.
    from openai import OpenAI

    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY_MISSING")

    model = os.getenv("OPENROUTER_MODEL", "openrouter/free").strip() or "openrouter/free"
    client = OpenAI(base_url="https://openrouter.ai/api/v1", api_key=api_key)
    user_payload = json.dumps({"message": message, "puzzle_id": puzzle_id}, ensure_ascii=False)

    kwargs = dict(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_payload},
        ],
        temperature=0,
        max_tokens=350,
    )

    headers = {}
    if os.getenv("OPENROUTER_SITE_URL"):
        headers["HTTP-Referer"] = os.getenv("OPENROUTER_SITE_URL")
    if os.getenv("OPENROUTER_APP_NAME"):
        headers["X-Title"] = os.getenv("OPENROUTER_APP_NAME")
    if headers:
        kwargs["extra_headers"] = headers

    # free router에서 response_format을 지원하지 않는 모델이 선택될 수 있어 2단계 fallback
    try:
        response = client.chat.completions.create(
            **kwargs,
            response_format={"type": "json_object"},
        )
    except Exception:
        response = client.chat.completions.create(**kwargs)

    content = response.choices[0].message.content or "{}"
    return _normalize(_extract_json(content), "openrouter", model)


def _baseline(message: str, puzzle_id: str | None) -> IntentResult:
    result = classify_intent_baseline(message)
    result.recommended_tools = (
        ["report_equipment_issue"]
        if result.intent == IntentType.EQUIPMENT_ISSUE
        else ["request_game_master"]
        if result.intent == IntentType.MASTER_REQUEST
        else ["get_game_session", "get_puzzle_context", "get_hint_history"]
        if result.intent == IntentType.HINT and puzzle_id
        else []
    )
    result.provider = "baseline"
    result.model = "baseline"
    return result


def analyze_user_request(
    message: str,
    puzzle_id: str | None = None,
    provider: str | None = None,
) -> IntentResult:
    selected = (provider or os.getenv("LLM_PROVIDER", "baseline")).lower()

    try:
        if selected == "baseline":
            return _baseline(message, puzzle_id)
        if selected == "openrouter":
            return _openrouter(message, puzzle_id)
        raise ValueError(f"UNSUPPORTED_LLM_PROVIDER:{selected}")
    except Exception:
        if os.getenv("LLM_FALLBACK_PROVIDER", "baseline").lower() == "baseline":
            result = _baseline(message, puzzle_id)
            result.provider = "baseline-fallback"
            return result
        raise
