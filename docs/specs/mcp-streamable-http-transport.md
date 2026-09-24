# MCP Streamable HTTP Transport

## Why

현재 `backend.services.mcp_client.MCPClient`는 MCP 서버와 통신하지 않고 `mcp_server.tools`의 Python 함수를 같은 프로세스에서 직접 호출한다. 이 상태에서는 FastMCP의 Tool schema·초기화·오류 응답·transport 경계를 실제로 검증할 수 없으며, LLM 기반 운영 자동화가 표준 MCP 호출로 실행된다는 증거도 남지 않는다.

## Goal

- 고객 Agent용 핵심 Tool 6개를 Streamable HTTP를 통해 호출할 수 있다.
- FastAPI adapter는 MCP Tool 구현 함수를 직접 import하지 않고 transport 인터페이스에만 의존한다.
- 기존 단위 테스트와 로컬 개발을 위해 인프로세스 transport를 기본값으로 유지한다.
- 실제 HTTP 소켓을 사용하는 통합 테스트 1건 이상으로 초기화·Tool 호출·structured output을 검증한다.
- MCP 서버 연결 실패와 Tool 오류를 고객에게 내부 스택 트레이스 없이 안전한 예외로 변환한다.

Out of Scope:

- Docker Compose의 `mcp` 서비스 분리
- 장기 연결·연결 풀·자동 재연결
- 인증·OAuth·TLS 종료
- 운영자 전용 Tool의 MCP 공개
- LLM·힌트 정책 변경

## What

### Happy Path

1. `MCP_CLIENT_TRANSPORT=streamable-http`와 `MCP_SERVER_URL`을 설정한다.
2. FastAPI adapter가 MCP 서버와 초기화 handshake를 수행한다.
3. adapter가 `{ "input": ... }` schema로 Tool을 호출한다.
4. `structuredContent`를 Python `dict`로 반환한다.
5. Orchestrator는 기존 서비스 메서드의 의미를 유지한 채 결과를 사용한다.

### Local Compatibility

환경변수를 설정하지 않으면 인프로세스 FastMCP registry를 사용한다. 이 경로도 등록된 Tool schema와 wrapper를 통과하지만 네트워크를 사용하지 않는다. Docker 서비스 분리 전까지 기존 개발·테스트의 기본 경로로 사용한다.

### Edge Case

- MCP 서버 URL이 없거나 transport 값이 잘못되면 시작 시 명확한 설정 오류를 반환한다.
- 연결 실패·시간 초과는 `MCP_SERVER_UNAVAILABLE` 연결 오류로 정규화한다.
- `isError=true` Tool 결과는 허용된 도메인 오류 코드만 상위 예외로 변환한다.
- `structuredContent`가 없거나 객체가 아니면 `MCP_INVALID_STRUCTURED_OUTPUT`으로 실패한다.
- sync adapter를 실행 중인 asyncio event loop 안에서 직접 호출하지 않는다.

## How

- `backend/services/mcp_transport.py`에 공통 `call_tool(name, input_data)` Protocol을 정의한다.
- `InProcessMCPTransport`는 `mcp_server.server.mcp.call_tool()`을 호출해 기존 로컬 실행을 보존한다.
- `StreamableHTTPMCPTransport`는 MCP Python SDK 1.x의 `streamable_http_client`와 `ClientSession`을 사용한다.
- `backend/services/mcp_client.py`는 핵심 6개 Tool을 transport에 위임한다.
- 세션 생성·진도 변경·운영자 큐 상태 변경은 참가자용 MCP 공개 범위가 아니므로 기존 내부 함수 호출을 유지한다.
- 서버 실행 시 `MCP_SERVER_TRANSPORT`, `MCP_SERVER_HOST`, `MCP_SERVER_PORT` 환경변수를 읽는다.
- 실제 HTTP 통합 테스트는 임시 포트에서 FastMCP ASGI app을 실행한 뒤 세션 상태 Tool을 호출한다.

## AC

### AC-01 직접 import 제거

GIVEN FastAPI의 `MCPClient`가 있고
WHEN 고객 Agent용 6개 메서드의 의존성을 검사하면
THEN `mcp_server.tools.hint_tools`, `puzzle_tools`, `request_game_master` 구현을 직접 호출하지 않고 transport를 사용한다.

### AC-02 실제 HTTP 왕복

GIVEN 임시 포트에서 실행 중인 FastMCP Streamable HTTP 서버와 유효한 세션이 있고
WHEN HTTP transport로 `get_game_session`을 호출하면
THEN MCP 초기화와 Tool 호출을 거쳐 세션의 structured output이 반환된다.

### AC-03 연결 실패

GIVEN 연결할 수 없는 MCP URL이 있고
WHEN Tool을 호출하면
THEN `ConnectionError("MCP_SERVER_UNAVAILABLE")`가 반환되고 내부 네트워크 예외 문자열은 외부 응답에 포함되지 않는다.

### AC-04 도메인 오류 보존

GIVEN 다른 팀의 세션으로 Tool을 호출했고
WHEN MCP 서버가 `TEAM_SESSION_MISMATCH`를 반환하면
THEN adapter는 이를 `PermissionError`로 변환한다.

### AC-05 회귀 방지

GIVEN 기존 백엔드 테스트와 신규 transport 테스트가 있고
WHEN 전체 테스트를 실행하면
THEN 모든 테스트가 통과한다.
