"""ANSWER 공개 정책.

현재 MVP에서는 고객의 명시적 동의만 허용한다. 자동 공개 조건은 후속 실험을
위해 코드로 분리하되, 기본 플래그를 False로 고정해 실수로 활성화되지 않게 한다.
"""
from backend.schemas import SessionState


ANSWER_AUTO_DELIVERY_ENABLED = False
ANSWER_AUTO_TIME_THRESHOLD_MINUTES = 5
ANSWER_AUTO_REMAINING_PUZZLES_THRESHOLD = 2


def should_auto_deliver_answer(
    session: SessionState,
    remaining_time_minutes: float,
) -> bool:
    """후속 자동 ANSWER 정책의 판정 지점. MVP에서는 항상 False다."""
    # 수정 사유: 시간 부족과 잔여 퍼즐이 많을 때의 자동 제공 후보를 분리하되,
    # 고객 동의 없는 정답 노출은 현재 금지하므로 feature flag를 먼저 검사한다.
    if not ANSWER_AUTO_DELIVERY_ENABLED or session.is_closed:
        return False
    return (
        remaining_time_minutes <= ANSWER_AUTO_TIME_THRESHOLD_MINUTES
        and session.remaining_puzzles >= ANSWER_AUTO_REMAINING_PUZZLES_THRESHOLD
    )
