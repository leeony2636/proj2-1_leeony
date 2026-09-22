from backend.schemas import HintDecision, HintStrength, SessionState, SupportNeed


def select_approved_hint_strength(
    *,
    session: SessionState,
    remaining_time_minutes: float,
    support_need: SupportNeed,
) -> HintDecision:
    """LLM 판단을 승인된 힌트 데이터의 표현 단계로 매핑한다.

    이 함수는 `support_need`가 도메인상 적절한지 다시 판정하지 않는다.
    강도 판단의 의미 품질은 사람이 정한 Domain Skill/평가셋으로 평가하고,
    코드는 승인된 WEAK/STRONG 이외의 자유 힌트 생성만 막는다.

    미확정인 숫자 시간/진도 규칙과 자동 재요청 승격은 적용하지 않는다.
    """
    if support_need in {SupportNeed.STRONG, SupportNeed.ANSWER}:
        strength = HintStrength.STRONG
        reason = f"LLM_SUPPORT_NEED_{support_need.value}_MAPPED_TO_APPROVED_STRONG"
    else:
        strength = HintStrength.WEAK
        reason = "LLM_SUPPORT_NEED_STANDARD_MAPPED_TO_APPROVED_WEAK"

    return HintDecision(
        strength=strength,
        reason_codes=[reason],
        remaining_time_minutes=remaining_time_minutes,
        remaining_puzzles=session.remaining_puzzles,
        remaining_puzzle_ratio=session.remaining_puzzle_ratio,
        solved_puzzle_ratio=session.solved_puzzle_ratio,
    )


# 이전 테스트/호출부가 남아 있을 때 실패 원인을 명확하게 하기 위한 호환 alias.
def enforce_hint_policy(**kwargs) -> HintDecision:
    return select_approved_hint_strength(**kwargs)
