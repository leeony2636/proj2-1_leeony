from backend.schemas import ConversationTurn, HintEvent
from mcp_server.tools.context_tools import get_conversation_history, record_conversation_turn
from mcp_server.tools.hint_tools import get_approved_hint, get_hint_history, record_hint_delivery
from mcp_server.tools.master_tools import (
    get_master_request_status,
    get_master_requests,
    report_equipment_issue,
    request_game_master,
    update_master_request,
)
from mcp_server.tools.puzzle_tools import get_puzzle_context
from mcp_server.tools.session_tools import create_game_session, get_game_session, list_themes, mark_puzzle_solved


class MCPClient:
    def list_themes(self): return list_themes()
    def create_session(self, theme_id, team_id): return create_game_session(theme_id, team_id)
    def get_session(self, session_id): return get_game_session(session_id)
    def solve(self, session_id, puzzle_id): return mark_puzzle_solved(session_id, puzzle_id)
    def get_puzzle(self, theme_id, puzzle_id): return get_puzzle_context(theme_id, puzzle_id)
    def get_history(self, session_id, puzzle_id): return get_hint_history(session_id, puzzle_id)
    def get_hint(self, theme_id, puzzle_id, strength): return get_approved_hint(theme_id, puzzle_id, strength)
    def record_hint(self, event: HintEvent):
        return record_hint_delivery(
            event.session_id,
            event.team_id,
            event.puzzle_id,
            event.strength.value,
            event.delivered_at.isoformat(),
            event.reason_codes,
            event.idempotency_key,
        )
    def call_master(self, session_id, team_id, reason, idempotency_key=None):
        return request_game_master(session_id, team_id, reason, idempotency_key)
    def equipment(self, session_id, team_id, detail, idempotency_key=None):
        return report_equipment_issue(session_id, team_id, detail, idempotency_key)
    def master_requests(self): return get_master_requests()
    def master_request_status(self, session_id, team_id, limit=5):
        return get_master_request_status(session_id, team_id, limit)
    def update_master_request(self, request_id, status, operator_id, note="", idempotency_key=None):
        return update_master_request(request_id, status, operator_id, note, idempotency_key)
    def get_conversation_history(self, session_id, limit=6):
        return [ConversationTurn.model_validate(item) for item in get_conversation_history(session_id, limit)]
    def record_conversation_turn(self, session_id, role, content, request_id=None):
        return record_conversation_turn(session_id, role, content, request_id)
