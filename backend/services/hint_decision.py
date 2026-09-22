from backend.schemas import HintDecision, HintStrength, SessionState


STRONG_TIME_MINUTES = 15
STRONG_REMAINING_PUZZLE_RATIO_MINIMUM = 0.50


def decide_hint_strength(
    session: SessionState,
    remaining_time_minutes: float,
    *,
    direct_answer_request: bool = False,
    strong_hint_request: bool = False,
    frustration_high: bool = False,
) -> HintDecision:
    """최신 팀 기획안의 명시적 규칙만 코드화한다.

    우선순위:
    1) 정답 직접 요구 / 강한 힌트 직접 요구 -> STRONG
    2) 강한 좌절 신호 -> STRONG
    3) 남은 시간 <= 15분 AND 남은 문제 비율 >= 50% -> STRONG
    4) 그 외 -> WEAK

    LLM은 이 함수의 최종 결과를 바꿀 수 없다.
    """
    reason_codes: list[str] = []

    if direct_answer_request:
        strength = HintStrength.STRONG
        reason_codes.append("DIRECT_ANSWER_REQUEST_STRONG")
    elif strong_hint_request:
        strength = HintStrength.STRONG
        reason_codes.append("DIRECT_STRONG_HINT_REQUEST")
    elif frustration_high:
        strength = HintStrength.STRONG
        reason_codes.append("HIGH_FRUSTRATION_STRONG")
    elif (
        remaining_time_minutes <= STRONG_TIME_MINUTES
        and session.remaining_puzzle_ratio >= STRONG_REMAINING_PUZZLE_RATIO_MINIMUM
    ):
        strength = HintStrength.STRONG
        reason_codes.append("TIME_PROGRESS_STRONG_RULE")
    else:
        strength = HintStrength.WEAK
        reason_codes.append("DEFAULT_WEAK_RULE")

    return HintDecision(
        strength=strength,
        reason_codes=reason_codes,
        remaining_time_minutes=remaining_time_minutes,
        remaining_puzzles=session.remaining_puzzles,
        remaining_puzzle_ratio=session.remaining_puzzle_ratio,
        solved_puzzle_ratio=session.solved_puzzle_ratio,
    )
