from mcp.server.fastmcp import FastMCP

from mcp_server.tools.hint_tools import get_approved_hint, get_hint_history, record_hint_delivery
from mcp_server.tools.master_tools import get_master_request_status, get_master_requests, report_equipment_issue, request_game_master, update_master_request
from mcp_server.tools.puzzle_tools import get_puzzle_context
from mcp_server.tools.session_tools import create_game_session, get_game_session, list_themes

mcp = FastMCP("escape-room-agent-mcp")

# temp-git의 실제 도구 구현을 현재 MCP 서버에 연결했습니다.
# FastAPI 내부 호출과 원격 FastMCP transport는 MCPClient에서 나중에 분리합니다.
# 힌트 도구는 승인 콘텐츠 조회/기록만 노출한다. 정답 공개는 AnswerVault/동의 경계로 분리한다.
for tool in (list_themes, create_game_session, get_game_session, get_puzzle_context, get_hint_history, get_approved_hint, record_hint_delivery, request_game_master, report_equipment_issue, get_master_requests, get_master_request_status, update_master_request):
    mcp.tool()(tool)

if __name__ == "__main__":
    mcp.run()
