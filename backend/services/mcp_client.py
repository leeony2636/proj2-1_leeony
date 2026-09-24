from __future__ import annotations

from uuid import NAMESPACE_URL, uuid4, uuid5

from backend.schemas import ConversationTurn, HintEvent, MasterRequestReason
from backend.services.mcp_transport import MCPTransport, build_mcp_transport
from mcp_server.tools.context_tools import (
    get_conversation_history,
    record_conversation_turn,
)
from mcp_server.tools.master_tools import (
    get_master_requests,
    update_master_request,
)
from mcp_server.tools.session_tools import (
    create_game_session,
    get_game_session,
    list_themes,
    mark_puzzle_solved,
)


_MASTER_REASONS = {reason.value for reason in MasterRequestReason}


def _normalize_master_reason(reason: str) -> tuple[str, bool]:
    """정확히 알려진 enum만 인정한다. 부분 문자열로 사유를 추측하지 않는다."""
    value = reason.strip().upper()
    if value in _MASTER_REASONS:
        return value, False
    return MasterRequestReason.UNKNOWN.value, True


class MCPClient:
    """FastAPI 서비스가 참가자용 MCP Tool과 내부 운영 함수를 구분해 호출한다."""

    def __init__(self, transport: MCPTransport | None = None) -> None:
        self.transport = transport or build_mcp_transport()

    # 테마·세션 생성과 운영자 큐 관리는 참가자용 핵심 6개 Tool 범위 밖의 내부 함수다.
    def list_themes(self) -> list[dict]:
        return list_themes()

    def create_session(self, theme_id: str, team_id: str) -> dict:
        return create_game_session(theme_id, team_id)

    def get_session(self, session_id: str) -> dict:
        return get_game_session(session_id)

    def solve(self, session_id: str, puzzle_id: str) -> dict:
        return mark_puzzle_solved(session_id, puzzle_id)

    def master_requests(self) -> list[dict]:
        return get_master_requests()

    def master_request_status(
        self,
        session_id: str,
        team_id: str,
        limit: int = 5,
    ) -> list[dict]:
        result = self.transport.call_tool(
            "get_master_request_status",
            {"session_id": session_id, "team_id": team_id, "limit": limit},
        )
        rows = result.get("requests")
        if not isinstance(rows, list):
            raise TypeError("MCP_MASTER_REQUEST_STATUS_INVALID")
        return rows

    def update_master_request(
        self,
        request_id: str,
        status: str,
        operator_id: str,
        note: str = "",
        idempotency_key: str | None = None,
    ) -> dict:
        return update_master_request(
            request_id,
            status,
            operator_id,
            note,
            idempotency_key,
        )

    def get_agent_session(self, session_id: str, team_id: str) -> dict:
        return self.transport.call_tool(
            "get_game_session",
            {"session_id": session_id, "team_id": team_id},
        )

    def get_puzzle(self, session_id: str, team_id: str, puzzle_id: str) -> dict:
        return self.transport.call_tool(
            "get_puzzle_context",
            {
                "session_id": session_id,
                "team_id": team_id,
                "puzzle_id": puzzle_id,
            },
        )

    def get_history(
        self,
        session_id: str,
        team_id: str,
        puzzle_id: str,
        limit: int = 20,
    ) -> list[dict]:
        result = self.transport.call_tool(
            "get_hint_history",
            {
                "session_id": session_id,
                "team_id": team_id,
                "puzzle_id": puzzle_id,
                "limit": limit,
            },
        )
        events = result.get("events")
        if not isinstance(events, list):
            raise TypeError("MCP_HINT_HISTORY_INVALID")
        return events

    def get_hint(
        self,
        session_id: str,
        team_id: str,
        puzzle_id: str,
        strength: str,
    ) -> str:
        result = self.transport.call_tool(
            "get_approved_hint",
            {
                "session_id": session_id,
                "team_id": team_id,
                "puzzle_id": puzzle_id,
                "hint_strength": strength,
            },
        )
        hint_text = result.get("hint_text")
        if not isinstance(hint_text, str) or not hint_text:
            raise TypeError("MCP_APPROVED_HINT_INVALID")
        return hint_text

    def record_hint(self, event: HintEvent) -> dict:
        idempotency_key = event.idempotency_key or (
            "legacy:"
            + uuid5(
                NAMESPACE_URL,
                "|".join(
                    (
                        event.session_id,
                        event.team_id,
                        event.puzzle_id,
                        event.strength.value,
                        event.delivered_at.isoformat(),
                    )
                ),
            ).hex
        )
        return self.transport.call_tool(
            "record_hint_delivery",
            {
                "session_id": event.session_id,
                "team_id": event.team_id,
                "puzzle_id": event.puzzle_id,
                "hint_strength": event.strength.value,
                "delivered_at": event.delivered_at.isoformat(),
                "reason_codes": event.reason_codes,
                "idempotency_key": idempotency_key,
            },
        )

    def call_master(
        self,
        session_id: str,
        team_id: str,
        reason: str,
        idempotency_key: str | None = None,
        puzzle_id: str | None = None,
        summary: str | None = None,
    ) -> dict:
        mapped_reason, unmapped = _normalize_master_reason(reason)
        preserved_summary = summary if summary is not None else reason
        request = {
            "session_id": session_id,
            "team_id": team_id,
            "puzzle_id": puzzle_id,
            "reason": mapped_reason,
            "summary": str(preserved_summary)[:300],
            "idempotency_key": idempotency_key or f"auto:{uuid4().hex}",
        }
        # unmapped 여부는 저장 단계에서 UNKNOWN reason + 원문 summary로 보존된다.
        _ = unmapped
        return self.transport.call_tool("request_game_master", request)

    def equipment(
        self,
        session_id: str,
        team_id: str,
        detail: str,
        idempotency_key: str | None = None,
        puzzle_id: str | None = None,
    ) -> dict:
        return self.call_master(
            session_id=session_id,
            team_id=team_id,
            reason="PROP_ERROR",
            summary=detail,
            idempotency_key=idempotency_key,
            puzzle_id=puzzle_id,
        )

    def get_conversation_history(
        self,
        session_id: str,
        limit: int = 6,
    ) -> list[ConversationTurn]:
        return [
            ConversationTurn.model_validate(item)
            for item in get_conversation_history(session_id, limit)
        ]

    def record_conversation_turn(
        self,
        session_id: str,
        role: str,
        content: str,
        request_id: str | None = None,
    ) -> dict:
        return record_conversation_turn(session_id, role, content, request_id)
