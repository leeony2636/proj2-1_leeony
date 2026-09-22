from fastapi import APIRouter, HTTPException

from backend.schemas import CreateSessionRequest
from backend.services.mcp_client import MCPClient

router = APIRouter(prefix="/api", tags=["sessions"])
mcp = MCPClient()


@router.get("/themes")
def themes() -> dict:
    return {"themes": mcp.list_themes()}


@router.post("/sessions")
def create_session(payload: CreateSessionRequest) -> dict:
    try:
        session = mcp.create_session(payload.theme_id, payload.team_id)
    except (KeyError, ValueError) as exc:
        raise HTTPException(400, str(exc)) from exc
    # 수정 기획안: MVP는 임시 session_id/team_id 방식만 사용한다. QR은 후속 범위다.
    return {"session": session}


@router.get("/sessions/{session_id}")
def read_session(session_id: str) -> dict:
    try:
        return mcp.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(404, str(exc)) from exc


# 고객 Agent가 진도를 직접 변경하면 안 되므로 P0에 public solve route를 두지 않는다.
# mark_puzzle_solved는 게임마스터/내부 이벤트 계약이 확정될 때까지 Runtime 내부 기능으로만 유지한다.
