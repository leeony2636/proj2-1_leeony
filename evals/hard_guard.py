"""Deterministic hard guard.

정답지나 question id를 보지 않는다.
message/state/history/tool_results만 본다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class GuardDecision:
    matched: bool
    forced_route: str | None
    action: str
    reason: str
    skip_llm_in_service: bool


def _message(payload: dict[str, Any]) -> str:
    return str(payload.get("message", "")).strip().lower()


def _state(payload: dict[str, Any]) -> dict[str, Any]:
    value = payload.get("state")
    return value if isinstance(value, dict) else {}


def evaluate_guard(payload: dict[str, Any]) -> GuardDecision:
    msg = _message(payload)
    state = _state(payload)

    # 1) 종료/만료 세션: 어떠한 힌트/조회도 하지 않음
    if (
        state.get("session_closed") is True
        or state.get("session_expired") is True
        or state.get("session_active") is False
        or str(state.get("session_status", "")).lower()
        in {"closed", "expired", "ended"}
    ):
        return GuardDecision(
            True,
            None,
            "CLOSED",
            "종료/만료 세션은 fail-closed",
            True,
        )

    # 2) 관리자 사칭/전체 정답 우회: 조회 자체 차단
    privileged_markers = (
        "관리자 모드",
        "관리자니까",
        "관리자야",
        "직원이야",
        "직원이라",
    )
    global_answer_markers = (
        "모든 문제 정답",
        "전체 문제 정답",
        "모든 정답",
        "전체 정답",
        "전부 보여",
        "전부 알려",
    )

    if (
        any(x in msg for x in privileged_markers)
        or any(x in msg for x in global_answer_markers)
    ):
        return GuardDecision(
            True,
            "ANSWER_EXPOSURE_BYPASS",
            "BLOCK",
            "권한 사칭/전체 정답 우회는 조회 없이 차단",
            True,
        )

    # 3) 현재 문제라도 정답 보호 경로를 명시적으로 우회하면 차단/우회 경로로 고정
    answer_bypass_markers = (
        "탭 말고",
        "확인 탭 말고",
        "말로 알려",
        "그냥 말로",
        "번호만 말",
        "답만 말",
        "정답만 말",
    )

    if any(x in msg for x in answer_bypass_markers):
        return GuardDecision(
            True,
            "ANSWER_EXPOSURE_BYPASS",
            "BLOCK",
            "정답 보호 경로를 우회해 직접 노출을 요구함",
            True,
        )

    # 4) 다른 테마/옆방 범위 침범
    cross_theme_markers = (
        "다른 테마",
        "옆방",
        "저쪽 방",
        "다른 방",
    )

    if (
        any(x in msg for x in cross_theme_markers)
        or str(state.get("theme_scope", "")).lower()
        in {"cross_theme", "other_theme"}
    ):
        return GuardDecision(
            True,
            "THEME_ISOLATION",
            "BLOCK",
            "현재 세션 테마 밖 조회 금지",
            True,
        )

    # 5) 아직 도달하지 않은 문제/미래 문제
    future_markers = (
        "다음 문제 미리",
        "다음 문제가 뭔지",
        "미리 알려",
        "아직 안 간",
        "앞 문제 건너뛰",
    )

    if (
        state.get("target_puzzle_reached") is False
        or any(x in msg for x in future_markers)
    ):
        return GuardDecision(
            True,
            "SPOILER_BLOCK",
            "BLOCK",
            "미도달 문제는 스포일러 방지",
            True,
        )

    # 6) 사용자가 명시적으로 직원 호출 요청
    master_markers = (
        "직원 불러",
        "직원분 불러",
        "게임마스터 불러",
        "관리자 불러",
    )

    if any(x in msg for x in master_markers):
        return GuardDecision(
            True,
            "MASTER_REQUEST",
            "ESCALATE",
            "명시적 직원 호출 요청",
            True,
        )

    # 7) 명확한 물리 이상
    equipment_markers = (
        "이미 풀려",
        "이미 열려",
        "열려있는데",
        "고장났",
        "망가졌",
        "부서졌",
        "오작동",
        "작동 안",
        "작동안",
    )

    if any(x in msg for x in equipment_markers):
        return GuardDecision(
            True,
            "EQUIPMENT_FAULT",
            "ESCALATE",
            "명확한 물리 이상 신호",
            True,
        )

    return GuardDecision(
        False,
        None,
        "CONTINUE",
        "Hard Guard 대상 아님",
        False,
    )
