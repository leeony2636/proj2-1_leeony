from __future__ import annotations

from contextlib import closing
from datetime import datetime, timezone
import socket
import threading
import time

import pytest
import uvicorn

from backend.schemas import HintEvent, HintStrength
from backend.services.mcp_client import MCPClient
from backend.services.mcp_transport import StreamableHTTPMCPTransport
from mcp_server.server import mcp
from mcp_server.tools.session_tools import create_game_session


def _unused_local_port() -> int:
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_until_started(server: uvicorn.Server, timeout_seconds: float = 5.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while not server.started and time.monotonic() < deadline:
        time.sleep(0.01)
    if not server.started:
        raise TimeoutError("MCP_TEST_SERVER_START_TIMEOUT")


@pytest.fixture(scope="module")
def http_mcp_client():
    """실제 로컬 소켓에서 FastMCP ASGI 앱을 실행해 HTTP 경계를 검증한다."""
    port = _unused_local_port()
    server = uvicorn.Server(
        uvicorn.Config(
            mcp.streamable_http_app(),
            host="127.0.0.1",
            port=port,
            log_level="error",
        )
    )
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    _wait_until_started(server)

    try:
        yield MCPClient(
            StreamableHTTPMCPTransport(f"http://127.0.0.1:{port}/mcp", 5.0)
        )
    finally:
        server.should_exit = True
        thread.join(timeout=5)


def test_core_tools_round_trip_over_streamable_http(http_mcp_client: MCPClient):
    session = create_game_session("last_train", "team-http-round-trip")
    session_id = session["session_id"]
    team_id = session["team_id"]
    puzzle_id = session["current_puzzle_id"]

    assert http_mcp_client.get_agent_session(session_id, team_id)["theme_id"] == "last_train"
    assert http_mcp_client.get_puzzle(session_id, team_id, puzzle_id)["puzzle_id"] == puzzle_id
    assert http_mcp_client.get_history(session_id, team_id, puzzle_id) == []
    assert http_mcp_client.get_hint(session_id, team_id, puzzle_id, "WEAK")

    event = HintEvent(
        session_id=session_id,
        team_id=team_id,
        puzzle_id=puzzle_id,
        strength=HintStrength.WEAK,
        delivered_at=datetime.now(timezone.utc),
        reason_codes=["HTTP_INTEGRATION_TEST"],
        idempotency_key=f"http-test:{session_id}",
    )
    first = http_mcp_client.record_hint(event)
    second = http_mcp_client.record_hint(event)
    assert first == {"ok": True, "deduplicated": False}
    assert second == {"ok": True, "deduplicated": True}

    request = http_mcp_client.call_master(
        session_id,
        team_id,
        "DIRECT_REQUEST",
        f"http-master:{session_id}",
    )
    assert request["status"] == "OPEN"


def test_streamable_http_preserves_safe_domain_error(http_mcp_client: MCPClient):
    session = create_game_session("last_train", "team-http-owner")

    with pytest.raises(PermissionError, match="TEAM_SESSION_MISMATCH"):
        http_mcp_client.get_agent_session(session["session_id"], "team-http-other")


def test_streamable_http_connection_failure_is_sanitized():
    port = _unused_local_port()
    transport = StreamableHTTPMCPTransport(f"http://127.0.0.1:{port}/mcp", 0.2)

    with pytest.raises(ConnectionError, match="^MCP_SERVER_UNAVAILABLE$"):
        transport.call_tool(
            "get_game_session",
            {"session_id": "missing", "team_id": "missing"},
        )
