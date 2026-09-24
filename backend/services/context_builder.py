from datetime import datetime, timezone

from backend.schemas import AgentContext, SessionState
from backend.services.domain_skill import build_llm_skill_context
from backend.services.mcp_client import MCPClient


def remaining_time_minutes(session: SessionState) -> float:
    elapsed = (datetime.now(timezone.utc) - session.started_at).total_seconds() / 60
    return max(session.duration_minutes - elapsed, 0.0)


def build_agent_context(
    mcp: MCPClient,
    *,
    session_id: str,
    team_id: str,
    requested_puzzle_id: str | None,
) -> tuple[SessionState, AgentContext]:
    """세션 경계와 최소 맥락만 먼저 구성한다.

    힌트 이력·운영 요청 상태처럼 상황에 따라 필요한 조회는 LLM이 읽기 전용
    lookup tool을 선택한 뒤에만 가져온다. 모든 요청에 고정 조회 순서를 강제하지 않는다.
    """
    # 세션/팀 권한 오류는 PermissionError로 유지해 API 403 경계와 구분한다.
    session = SessionState.model_validate(mcp.get_agent_session(session_id, team_id))

    # 서버 세션의 current_puzzle_id가 정본이다. 고객 puzzle_id는 호환을 위한
    # 후보값일 뿐이며, 불일치는 조용히 덮어쓰지 않고 LLM/MCP 조회 전에 종료한다.
    if (
        requested_puzzle_id is not None
        and session.current_puzzle_id is not None
        and requested_puzzle_id != session.current_puzzle_id
    ):
        raise ValueError("PUZZLE_ID_MISMATCH")

    effective_puzzle_id = session.current_puzzle_id
    puzzle_context = None
    if effective_puzzle_id and not session.is_closed:
        puzzle_context = mcp.get_puzzle(
            session.session_id,
            session.team_id,
            effective_puzzle_id,
        )

    context = AgentContext(
        session_id=session.session_id,
        team_id=session.team_id,
        theme_id=session.theme_id,
        current_puzzle_id=session.current_puzzle_id,
        requested_puzzle_id=effective_puzzle_id,
        remaining_time_minutes=remaining_time_minutes(session),
        puzzle_context=puzzle_context,
        recent_turns=mcp.get_conversation_history(session_id, limit=6),
        domain_skill=build_llm_skill_context(),
    )
    return session, context

