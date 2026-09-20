"""AnswerVault 전용 조회 경로.

일반 Agent 프롬프트나 MCP 힌트 Tool에서 이 파일을 읽지 않는다.
STRONG 힌트가 실제 전달된 뒤 사용자가 정답 확인을 직접 실행했을 때만 조회한다.
"""
from pathlib import Path
import json

from backend.schemas import HintStrength, SessionState
from backend.services.mcp_client import MCPClient


ROOT = Path(__file__).resolve().parents[2]
ANSWER_DIR = ROOT / "backend" / "data" / "answers"
mcp = MCPClient()


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

    path = ANSWER_DIR / f"{session.theme_id}.json"
    if not path.exists():
        raise KeyError(f"ANSWER_DATA_NOT_FOUND:{session.theme_id}")

    data = json.loads(path.read_text(encoding="utf-8"))
    if puzzle_id not in data:
        raise KeyError(f"ANSWER_NOT_FOUND:{puzzle_id}")

    item = data[puzzle_id]
    return {
        "puzzle_id": puzzle_id,
        "answer": item["answer"],
        "policy": "USER_EXPLICIT_REVEAL_AFTER_STRONG",
    }
