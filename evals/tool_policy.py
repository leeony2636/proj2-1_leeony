"""Deterministic MCP Tool policy.

금지:
- dataset / expected / question id 참조
- 모델 recommended_tools 신뢰
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ToolPlan:
    tools: tuple[str, ...]
    reason: str


HINT_TOOLS = (
    "get_puzzle_context",
    "get_approved_hint",
)

NO_TOOL_ROUTES = {
    "PROGRESS_ESTIMATION",
    "SPOILER_BLOCK",
    "THEME_ISOLATION",
}


def _message(payload: dict[str, Any]) -> str:
    return str(payload.get("message", "")).strip().lower()


def _state(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("state")
    return value if isinstance(value, dict) else {}


def _history(payload: dict[str, Any]) -> list[dict[str, Any]]:
    value = payload.get("history")
    if not isinstance(value, list):
        return []
    return [x for x in value if isinstance(x, dict)]


def _tool_results(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("tool_results")
    return value if isinstance(value, dict) else {}


def _previous_hint_exists(payload: dict[str, Any]) -> bool:
    state = _state(payload)

    if state.get("last_hint_strength"):
        return True

    return any(
        item.get("role") == "assistant"
        for item in _history(payload)
    )


def _history_already_available(payload: dict[str, Any]) -> bool:
    results = _tool_results(payload)
    return (
        "get_hint_history" in results
        or "hint_history" in results
    )


def _same_puzzle_not_false(payload: dict[str, Any]) -> bool:
    return _state(payload).get("last_hint_same_puzzle") is not False


def _strong_equipment_anomaly(payload: dict[str, Any]) -> bool:
    msg = _message(payload)

    markers = (
        "이미 풀려",
        "이미 열려",
        "열려있는데",
        "고장",
        "망가",
        "부서",
        "오작동",
        "작동 안",
        "작동안",
    )
    return any(x in msg for x in markers)


def _global_answer_bypass(payload: dict[str, Any]) -> bool:
    msg = _message(payload)

    markers = (
        "모든 문제 정답",
        "전체 문제 정답",
        "모든 정답",
        "전체 정답",
        "관리자 모드",
        "관리자니까",
        "직원이야",
    )
    return any(x in msg for x in markers)


def plan_tools(
    route: str,
    payload: dict[str, Any],
) -> ToolPlan:
    route = str(route).strip().upper()

    if route == "HINT_DECISION":
        tools: list[str] = []

        if (
            _previous_hint_exists(payload)
            and _same_puzzle_not_false(payload)
            and not _history_already_available(payload)
        ):
            tools.append("get_hint_history")

        tools.extend(HINT_TOOLS)

        return ToolPlan(
            tuple(tools),
            "힌트 경로: 현재 퍼즐 + 승인 힌트, 필요한 경우에만 힌트 이력",
        )

    if route in {
        "INPUT_LOCATION",
        "EQUIPMENT_USAGE",
        "PROGRESS_TRANSITION",
    }:
        return ToolPlan(
            ("get_puzzle_context",),
            "현재 퍼즐 맥락 조회",
        )

    if route == "MASTER_REQUEST":
        return ToolPlan(
            ("request_game_master",),
            "명시적 직원 호출",
        )

    if route == "EQUIPMENT_FAULT":
        if _strong_equipment_anomaly(payload):
            return ToolPlan(
                (
                    "get_puzzle_context",
                    "report_equipment_issue",
                    "request_game_master",
                ),
                "명확한 기구 이상: 맥락 확인 + 이상 신고 + 직원 호출",
            )

        return ToolPlan(
            ("get_puzzle_context",),
            "원인 미확인: 먼저 현재 퍼즐 맥락만 확인",
        )

    if route == "PROGRESS_VERIFICATION":
        return ToolPlan(
            ("get_game_session",),
            "비정상 진도 주장은 세션으로 검증",
        )

    if route in NO_TOOL_ROUTES:
        return ToolPlan(
            (),
            "확인/차단 우선 경로: Tool 호출 없음",
        )

    if route == "ANSWER_EXPOSURE_BYPASS":
        if _global_answer_bypass(payload):
            return ToolPlan(
                (),
                "전체 정답/권한 우회는 조회 없이 차단",
            )

        if _state(payload).get("current_puzzle_known") is True:
            return ToolPlan(
                HINT_TOOLS,
                "현재 문제 직접 정답 요구는 승인 힌트 경로로 제한",
            )

        return ToolPlan(
            (),
            "현재 문제를 안전하게 특정할 수 없어 조회하지 않음",
        )

    return ToolPlan(
        (),
        "알 수 없는 route: fail-closed",
    )


def validate_plan_against_registry(
    plan: ToolPlan,
    actual_tool_names: set[str],
) -> tuple[bool, list[str]]:
    missing = [
        name
        for name in plan.tools
        if name not in actual_tool_names
    ]
    return (len(missing) == 0, missing)
