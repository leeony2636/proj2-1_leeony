from datetime import datetime, timezone

from backend.schemas import HintStrength, SessionState
from backend.services.hint_decision import decide_hint_strength


def make_session(*, solved: int, total: int = 10) -> SessionState:
    return SessionState(
        session_id="s1",
        team_id="t1",
        theme_id="theme_demo",
        started_at=datetime.now(timezone.utc),
        duration_minutes=60,
        total_puzzles=total,
        solved_puzzles=solved,
        current_puzzle_id="p01",
    )


def test_exact_50_percent_is_not_time_progress_strong():
    result = decide_hint_strength(
        session=make_session(solved=5, total=10),
        remaining_time_minutes=15,
    )
    assert result.strength == HintStrength.WEAK


def test_strong_when_time_low_and_solved_under_50_percent():
    result = decide_hint_strength(
        session=make_session(solved=4, total=10),
        remaining_time_minutes=15,
    )
    assert result.strength == HintStrength.STRONG
    assert "TIME_PROGRESS_STRONG_RULE" in result.reason_codes


def test_direct_answer_request_is_strong():
    result = decide_hint_strength(
        session=make_session(solved=8, total=10),
        remaining_time_minutes=40,
        direct_answer_request=True,
    )
    assert result.strength == HintStrength.STRONG
    assert "DIRECT_ANSWER_REQUEST_STRONG" in result.reason_codes


def test_high_frustration_is_strong():
    result = decide_hint_strength(
        session=make_session(solved=8, total=10),
        remaining_time_minutes=40,
        frustration_high=True,
    )
    assert result.strength == HintStrength.STRONG
    assert "HIGH_FRUSTRATION_STRONG" in result.reason_codes


def test_default_is_weak():
    result = decide_hint_strength(
        session=make_session(solved=8, total=10),
        remaining_time_minutes=30,
    )
    assert result.strength == HintStrength.WEAK
