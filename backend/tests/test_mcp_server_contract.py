import asyncio

import pytest
from pydantic import ValidationError

from mcp_server.schemas import GetApprovedHintInput
from mcp_server.server import mcp
from mcp_server.tools.session_tools import create_game_session


CORE_TOOL_NAMES = {
    "get_game_session",
    "get_puzzle_context",
    "get_hint_history",
    "get_master_request_status",
    "get_approved_hint",
    "record_hint_delivery",
    "request_game_master",
}


def _registered_tools():
    return {tool.name: tool for tool in asyncio.run(mcp.list_tools())}


def _nested_input_schema(tool) -> dict:
    model_ref = tool.inputSchema["properties"]["input"]["$ref"]
    model_name = model_ref.rsplit("/", maxsplit=1)[-1]
    return tool.inputSchema["$defs"][model_name]


def test_server_registers_only_the_approved_customer_agent_tools():
    tools = _registered_tools()

    assert set(tools) == CORE_TOOL_NAMES


@pytest.mark.parametrize("tool_name", sorted(CORE_TOOL_NAMES))
def test_each_tool_publishes_strict_input_output_schema_and_complete_docstring(tool_name):
    tool = _registered_tools()[tool_name]

    assert _nested_input_schema(tool)["additionalProperties"] is False
    assert tool.outputSchema["additionalProperties"] is False
    for required_section in ("호출 조건:", "입력:", "반환:", "부작용:", "호출 금지:"):
        assert required_section in tool.description


def test_hint_tool_schema_allows_only_weak_or_strong():
    schema = _nested_input_schema(_registered_tools()["get_approved_hint"])
    enum_name = schema["properties"]["hint_strength"]["$ref"].rsplit("/", 1)[-1]
    root_defs = _registered_tools()["get_approved_hint"].inputSchema["$defs"]

    assert root_defs[enum_name]["enum"] == ["WEAK", "STRONG"]


def test_write_tools_require_idempotency_key():
    tools = _registered_tools()

    for tool_name in ("record_hint_delivery", "request_game_master"):
        assert "idempotency_key" in _nested_input_schema(tools[tool_name])["required"]


def test_input_models_reject_unknown_fields():
    with pytest.raises(ValidationError):
        GetApprovedHintInput.model_validate(
            {
                "session_id": "session-1",
                "team_id": "team-1",
                "puzzle_id": "puzzle-1",
                "hint_strength": "WEAK",
                "theme_id": "other-theme",
            }
        )


def test_registered_tools_execute_through_fastmcp_registry():
    session = create_game_session("last_train", "team-mcp-contract")
    common = {
        "session_id": session["session_id"],
        "team_id": session["team_id"],
    }
    puzzle = {**common, "puzzle_id": session["current_puzzle_id"]}

    async def call_scenario():
        calls = [
            ("get_game_session", common),
            ("get_puzzle_context", puzzle),
            ("get_hint_history", puzzle),
            ("get_approved_hint", {**puzzle, "hint_strength": "WEAK"}),
            (
                "record_hint_delivery",
                {
                    **puzzle,
                    "hint_strength": "WEAK",
                    "delivered_at": "2026-09-23T00:00:00+00:00",
                    "reason_codes": ["MEANING_BASED_WEAK"],
                    "idempotency_key": "contract-hint-delivery-1",
                },
            ),
            (
                "request_game_master",
                {
                    **puzzle,
                    "reason": "DIRECT_REQUEST",
                    "summary": "고객이 게임마스터 호출을 직접 요청함",
                    "idempotency_key": "contract-master-request-1",
                },
            ),
        ]
        for tool_name, input_data in calls:
            assert await mcp.call_tool(tool_name, {"input": input_data})
        # 같은 시각·키·payload 재호출은 새 이력을 만들지 않고 기존 결과를 재사용해야 한다.
        assert await mcp.call_tool("record_hint_delivery", {"input": calls[4][1]})

    asyncio.run(call_scenario())
