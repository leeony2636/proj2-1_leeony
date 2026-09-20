"""Deterministic Skill policy for the escape-room Agent.

LLM은 자연어 route/신호를 구조화한다.
최종 hint rule/strength는 이 코드가 결정한다.
expected/question_id/category/dataset은 참조하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any


@dataclass(frozen=True)
class SkillDecision:
    rule: str
    strength: str | None
    reason: str


_HINT_ROUTES = {
    "HINT_DECISION",
    "ANSWER_EXPOSURE_BYPASS",
}

_GLOBAL_PRIVILEGE_MARKERS = (
    "관리자 모드",
    "관리자니까",
    "직원이야",
    "직원이라",
    "모든 문제 정답",
    "전체 문제 정답",
    "모든 정답",
    "전체 정답",
    "전부 보여",
)

_TIME_OR_REPEAT_PATTERNS = (
    r"\d+\s*분(?:째)?",
    r"\d+\s*번",
    r"몇\s*번",
    r"여러\s*번",
    r"아까부터",
    r"계속",
    r"반복",
    r"한참",
    r"오래",
)

_HELPLESS_MARKERS = (
    "도저히",
    "모르겠",
    "못하겠",
    "막막",
    "감이 안",
    "어떻게 해야",
    "포기",
)


def _state(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("state")
    return value if isinstance(value, dict) else {}


def _message(payload: dict[str, Any]) -> str:
    return str(payload.get("message", "")).strip().lower()


def is_global_privilege_bypass(payload: dict[str, Any]) -> bool:
    msg = _message(payload)
    return any(marker in msg for marker in _GLOBAL_PRIVILEGE_MARKERS)


def qualifies_emotion_override(payload: dict[str, Any]) -> bool:
    """Skill.md의 '시간/반복시도 + 무력감' 복합조건을 코드로 판정."""
    msg = _message(payload)
    time_or_repeat = any(
        re.search(pattern, msg)
        for pattern in _TIME_OR_REPEAT_PATTERNS
    )
    helpless = any(
        marker in msg
        for marker in _HELPLESS_MARKERS
    )
    return bool(time_or_repeat and helpless)


def derive_skill_decision(
    route: str,
    payload: dict[str, Any],
    signals: dict[str, Any] | None = None,
) -> SkillDecision:
    """Skill.md 우선순위를 deterministic code로 계산한다.

    우선순위:
    ANSWER_REQUEST > RE_REQUEST_OVERRIDE > EMOTION_OVERRIDE
    > BASE_RULE_TIME_AND_PROGRESS > BASE_RULE_DEFAULT
    """
    route = str(route).strip().upper()
    state = _state(payload)
    signals = signals or {}

    # 힌트 강도 정책이 아닌 route에는 Skill rule을 붙이지 않는다.
    if route not in _HINT_ROUTES:
        return SkillDecision(
            "NONE",
            None,
            "힌트 강도 정책 비적용 route",
        )

    # 권한 사칭/전체 정답 우회는 fail-closed. 강한 힌트로 전환하지 않는다.
    if route == "ANSWER_EXPOSURE_BYPASS" and is_global_privilege_bypass(payload):
        return SkillDecision(
            "NONE",
            None,
            "권한 사칭/전체 정답 우회 → 힌트정책 비적용",
        )

    # 1) 현재 문제 정답 직접 요구
    if signals.get("direct_answer_request") is True:
        return SkillDecision(
            "ANSWER_REQUEST",
            "strong",
            "현재 문제 정답 직접 요구 → 승인된 강한 힌트 경로",
        )

    # 2) 같은 문제 약한 힌트 후 재요청
    re_request = state.get("re_request") is True
    if (
        not re_request
        and str(state.get("last_hint_strength", "")).lower() == "weak"
        and state.get("last_hint_same_puzzle") is True
    ):
        seconds = state.get("seconds_since_last_hint")
        if isinstance(seconds, (int, float)) and seconds <= 60:
            re_request = True

    if re_request:
        return SkillDecision(
            "RE_REQUEST_OVERRIDE",
            "strong",
            "같은 문제 약한 힌트 직후 재요청 → 강한 힌트 승격",
        )

    # 3) 감정 오버라이드: 모델 신호에 의존하지 않고 원문에서 독립 판정.
    if qualifies_emotion_override(payload):
        return SkillDecision(
            "EMOTION_OVERRIDE",
            "strong",
            "시간/반복시도 + 무력감 복합조건 충족",
        )

    # 4) 시간/남은 문제 비율 기본 규칙
    remaining_time = state.get("remaining_time_minutes")
    remaining_ratio = state.get("remaining_puzzle_ratio")

    if (
        isinstance(remaining_time, (int, float))
        and isinstance(remaining_ratio, (int, float))
        and remaining_time <= 15
        and remaining_ratio >= 0.50
    ):
        return SkillDecision(
            "BASE_RULE_TIME_AND_PROGRESS",
            "strong",
            "남은시간<=15분 AND 남은문제비율>=50%",
        )

    # 5) 그 외 일반 힌트
    return SkillDecision(
        "BASE_RULE_DEFAULT",
        "weak",
        "오버라이드 없음 → 기본 약한 힌트",
    )
