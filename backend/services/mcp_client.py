from backend.schemas import HintEvent
from mcp_server.tools.hint_tools import get_approved_hint,get_hint_history,record_hint_delivery
from mcp_server.tools.master_tools import get_master_requests,report_equipment_issue,request_game_master
from mcp_server.tools.puzzle_tools import get_puzzle_context
from mcp_server.tools.session_tools import create_game_session,get_game_session,list_themes,mark_puzzle_solved
class MCPClient:
    def list_themes(self): return list_themes()
    def create_session(self,theme_id,team_id): return create_game_session(theme_id,team_id)
    def get_session(self,session_id): return get_game_session(session_id)
    def solve(self,session_id,puzzle_id): return mark_puzzle_solved(session_id,puzzle_id)
    def get_puzzle(self,theme_id,puzzle_id): return get_puzzle_context(theme_id,puzzle_id)
    def get_history(self,session_id,puzzle_id): return get_hint_history(session_id,puzzle_id)
    def get_hint(self,theme_id,puzzle_id,strength): return get_approved_hint(theme_id,puzzle_id,strength)
    def record_hint(self,event:HintEvent): return record_hint_delivery(event.session_id,event.team_id,event.puzzle_id,event.strength.value,event.delivered_at.isoformat(),event.reason_codes)
    def call_master(self,session_id,team_id,reason): return request_game_master(session_id,team_id,reason)
    def equipment(self,session_id,team_id,detail): return report_equipment_issue(session_id,team_id,detail)
    def master_requests(self): return get_master_requests()
