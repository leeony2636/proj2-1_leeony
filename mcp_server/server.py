import os

from mcp.server.fastmcp import FastMCP

from mcp_server.contract_dispatch import dispatch_tool
from mcp_server.schemas import (
    ApprovedHintOutput,
    GameMasterRequestOutput,
    GameMasterRequestStatusOutput,
    GameSessionOutput,
    GetApprovedHintInput,
    GetGameSessionInput,
    GetHintHistoryInput,
    GetMasterRequestStatusInput,
    GetPuzzleContextInput,
    HintDeliveryOutput,
    HintHistoryOutput,
    PuzzleContextOutput,
    RecordHintDeliveryInput,
    RequestGameMasterInput,
)


mcp = FastMCP(
    "escape-room-agent-mcp",
    host=os.getenv("MCP_SERVER_HOST", "127.0.0.1"),
    port=int(os.getenv("MCP_SERVER_PORT", "8001")),
    json_response=True,
)


@mcp.tool()
def get_game_session(input: GetGameSessionInput) -> GameSessionOutput:
    """현재 참가 팀의 검증된 세션 상태를 조회한다.

    호출 조건: 서버가 보유한 session_id/team_id 조합을 확인할 때.
    입력: 검증 대상 session_id, team_id.
    반환: 검증된 세션 상태.
    부작용: 없음(읽기 전용).
    호출 금지: LLM이 식별자를 추측하거나 다른 팀 세션을 조회하려는 경우.
    """
    return GameSessionOutput.model_validate(dispatch_tool("get_game_session", input.model_dump(mode="json")))


@mcp.tool()
def get_puzzle_context(input: GetPuzzleContextInput) -> PuzzleContextOutput:
    """서버가 검증한 현재 문제의 비정답 메타데이터만 조회한다.

    호출 조건: 서버 current_puzzle_id와 일치하는 현재 문제 정보를 확인할 때.
    입력: session_id, team_id, puzzle_id.
    반환: 정답이 없는 현재 문제 컨텍스트.
    부작용: 없음(읽기 전용).
    호출 금지: 미래/다른 문제 또는 다른 팀 문제를 조회하려는 경우.
    """
    return PuzzleContextOutput.model_validate(dispatch_tool("get_puzzle_context", input.model_dump(mode="json")))


@mcp.tool()
def get_hint_history(input: GetHintHistoryInput) -> HintHistoryOutput:
    """현재 문제의 승인 힌트 제공 이력만 조회한다.

    호출 조건: 이전 힌트 제공 여부가 후속 의미 판단에 필요할 때.
    입력: session_id, team_id, puzzle_id, limit.
    반환: 승인 힌트 제공 이력(힌트 원문 제외).
    부작용: 없음(읽기 전용).
    호출 금지: 다른 팀/다른 문제 이력 또는 정답 원문을 얻으려는 경우.
    """
    return HintHistoryOutput.model_validate(dispatch_tool("get_hint_history", input.model_dump(mode="json")))


@mcp.tool()
def get_master_request_status(input: GetMasterRequestStatusInput) -> GameMasterRequestStatusOutput:
    """현재 세션/팀의 최근 게임마스터 요청 상태를 조회한다.

    호출 조건: '아까 직원 요청'처럼 기존 운영 요청 상태가 후속 판단에 필요할 때.
    입력: session_id, team_id, limit.
    반환: 현재 세션/팀에 한정된 최근 요청 상태.
    부작용: 없음(읽기 전용).
    호출 금지: 다른 팀 큐 조회나 운영자 전체 큐 노출 용도로 사용하려는 경우.
    """
    return GameMasterRequestStatusOutput.model_validate(
        dispatch_tool("get_master_request_status", input.model_dump(mode="json"))
    )


@mcp.tool()
def get_approved_hint(input: GetApprovedHintInput) -> ApprovedHintOutput:
    """코드가 허용한 WEAK/STRONG 승인 힌트만 조회한다.

    호출 조건: LLM 의미 판단 뒤 코드가 최종 허용 강도를 확정했을 때.
    입력: session_id, team_id, puzzle_id, hint_strength.
    반환: 승인된 힌트 원문과 강도.
    부작용: 없음(읽기 전용).
    호출 금지: ANSWER 정답 원문 생성, 미도달 문제, 승인되지 않은 힌트 생성.
    """
    return ApprovedHintOutput.model_validate(dispatch_tool("get_approved_hint", input.model_dump(mode="json")))


@mcp.tool()
def record_hint_delivery(input: RecordHintDeliveryInput) -> HintDeliveryOutput:
    """실제 제공한 승인 힌트 이력을 기록한다.

    호출 조건: 승인 힌트 조회가 성공하고 실제 고객 제공이 확정됐을 때.
    입력: session_id, team_id, puzzle_id, 강도, 시각, reason_codes, idempotency_key.
    반환: 기록 성공/중복 여부.
    부작용: 힌트 제공 이력 저장.
    호출 금지: LLM schema/policy 실패, 권한 실패, puzzle 불일치, 실제 제공 전.
    """
    return HintDeliveryOutput.model_validate(dispatch_tool("record_hint_delivery", input.model_dump(mode="json")))


@mcp.tool()
def request_game_master(input: RequestGameMasterInput) -> GameMasterRequestOutput:
    """게임마스터 운영 큐 요청을 생성한다.

    호출 조건: 검증된 세션/팀에서 코드가 허용한 직원 요청 action을 실행할 때.
    입력: session_id, team_id, optional puzzle_id, 제한 reason enum, bounded summary, idempotency_key.
    반환: 생성된 운영 요청과 상태.
    부작용: 운영 큐에 요청 저장.
    호출 금지: LLM schema/policy 실패, 인증/권한 실패, 식별자 불일치, 단순 조회 한도 도달만으로 자동 호출.
    """
    return GameMasterRequestOutput.model_validate(dispatch_tool("request_game_master", input.model_dump(mode="json")))


if __name__ == "__main__":
    transport = os.getenv("MCP_SERVER_TRANSPORT", "stdio").strip().lower()
    if transport not in {"stdio", "sse", "streamable-http"}:
        raise ValueError(f"MCP_SERVER_TRANSPORT_UNSUPPORTED:{transport}")
    mcp.run(transport=transport)
