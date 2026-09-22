"""AnswerVault 전용 조회 경로.

일반 Agent 프롬프트나 MCP 힌트 Tool에서 이 파일을 읽지 않는다.
STRONG 힌트가 실제 전달된 뒤 사용자가 일회성 동의 토큰을 확인했을 때만 조회한다.
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
import json
import uuid

from backend.schemas import HintStrength, SessionState
from backend.services.mcp_client import MCPClient


ROOT = Path(__file__).resolve().parents[2]
ANSWER_DIR = ROOT / "backend" / "data" / "answers"
mcp = MCPClient()
_ANSWER_OFFERS: dict[str, dict] = {}
_OFFER_TTL = timedelta(minutes=10)


def _validate_strong_hint(session_id: str, team_id: str, puzzle_id: str) -> SessionState:
    session = SessionState.model_validate(mcp.get_session(session_id))
    if session.team_id != team_id:
        raise ValueError("TEAM_SESSION_MISMATCH")
    if session.current_puzzle_id != puzzle_id:
        raise ValueError("ANSWER_REVEAL_CURRENT_PUZZLE_ONLY")

    history = mcp.get_history(session_id, puzzle_id)
    if not any(event.get("strength") == HintStrength.STRONG.value for event in history):
        raise PermissionError("STRONG_HINT_REQUIRED_BEFORE_ANSWER_CONFIRMATION")
    return session


def create_answer_offer(session_id: str, team_id: str, puzzle_id: str) -> dict:
    """STRONG 힌트가 전달된 뒤에만 일회성 정답 동의 토큰을 만든다."""
    _validate_strong_hint(session_id, team_id, puzzle_id)
    now = datetime.now(timezone.utc)
    offer_id = f"offer_{uuid.uuid4().hex}"
    expires_at = now + _OFFER_TTL
    _ANSWER_OFFERS[offer_id] = {
        "session_id": session_id,
        "team_id": team_id,
        "puzzle_id": puzzle_id,
        "expires_at": expires_at,
        "consumed": False,
    }
    return {"offer_id": offer_id, "offer_expires_at": expires_at}


def _load_answer(session: SessionState, puzzle_id: str) -> dict:
    path = ANSWER_DIR / f"{session.theme_id}.json"
    if not path.exists():
        raise KeyError(f"ANSWER_DATA_NOT_FOUND:{session.theme_id}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if puzzle_id not in data:
        raise KeyError(f"ANSWER_NOT_FOUND:{puzzle_id}")
    return data[puzzle_id]


def confirm_answer(session_id: str, team_id: str, puzzle_id: str, offer_id: str) -> dict:
    """offer_id와 명시적 확인 요청이 모두 유효할 때만 정답을 반환한다."""
    offer = _ANSWER_OFFERS.get(offer_id)
    if offer is None:
        raise PermissionError("ANSWER_OFFER_NOT_FOUND")
    if offer["consumed"]:
        raise PermissionError("ANSWER_OFFER_ALREADY_CONSUMED")
    if offer["expires_at"] <= datetime.now(timezone.utc):
        raise PermissionError("ANSWER_OFFER_EXPIRED")
    if any(
        offer[key] != value
        for key, value in {
            "session_id": session_id,
            "team_id": team_id,
            "puzzle_id": puzzle_id,
        }.items()
    ):
        raise PermissionError("ANSWER_OFFER_SCOPE_MISMATCH")

    session = _validate_strong_hint(session_id, team_id, puzzle_id)
    offer["consumed"] = True
    item = _load_answer(session, puzzle_id)
    return {
        "puzzle_id": puzzle_id,
        "answer": item["answer"],
        "policy": "USER_EXPLICIT_CONFIRMATION",
    }


def reveal_answer(session_id: str, team_id: str, puzzle_id: str) -> dict:
    session = SessionState.model_validate(mcp.get_session(session_id))
    if session.team_id != team_id:
        raise ValueError("TEAM_SESSION_MISMATCH")

    # 현재 퍼즐이 아닌 정답을 미리 보는 것을 차단한다.
    if session.current_puzzle_id != puzzle_id:
        raise ValueError("ANSWER_REVEAL_CURRENT_PUZZLE_ONLY")

    history = mcp.get_history(session_id, puzzle_id)
    has_strong = any(
        event.get("strength") == HintStrength.STRONG.value
        for event in history
    )
    if not has_strong:
        raise PermissionError("STRONG_HINT_REQUIRED_BEFORE_ANSWER_REVEAL")

    return {
        "puzzle_id": puzzle_id,
        "answer": _load_answer(session, puzzle_id),
        "policy": "USER_EXPLICIT_REVEAL_AFTER_STRONG",
    }
