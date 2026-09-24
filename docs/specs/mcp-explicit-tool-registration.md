# MCP 명시 등록·스키마 계약

## Why

기존 `server.py`는 구현 함수를 반복문으로 동적 등록해 자동 검사와 LLM이 Tool의 호출 조건·입력·부작용을 정적으로 확인하기 어려웠다. 또한 FastMCP 서버 경계에 출력 전용 모델이 없어 내부 반환 구조가 그대로 공개될 가능성이 있었다.

## Goal

- 고객 Agent용 핵심 MCP Tool을 정확히 6개만 명시적으로 등록한다.
- 6개 Tool 모두 엄격한 Pydantic 입력·출력 schema와 한국어 docstring을 제공한다.
- 읽기 Tool은 세션·팀·현재 문제 경계를 검증하고, 쓰기 Tool은 `idempotency_key`를 필수로 받는다.
- Tool 등록·schema·인메모리 호출 계약 테스트를 모두 통과한다.

Out of Scope:

- FastAPI와 MCP 서버 사이의 네트워크 transport
- Docker의 FastAPI/MCP 서비스 분리
- 운영자 전용 Tool 공개
- 기존 Runtime·Repository 비즈니스 로직 변경

## What

### Happy Path

`tools/list`에서 다음 6개 Tool과 각 description·입력 schema·출력 schema를 확인할 수 있다.

1. `get_game_session`
2. `get_puzzle_context`
3. `get_hint_history`
4. `get_approved_hint`
5. `record_hint_delivery`
6. `request_game_master`

각 Tool은 `input` 객체 하나를 받고 출력 전용 Pydantic 모델을 반환한다.

| Tool | `input` 필드 |
|---|---|
| `get_game_session` | `session_id`, `team_id` |
| `get_puzzle_context` | `session_id`, `team_id`, `puzzle_id` |
| `get_hint_history` | `session_id`, `team_id`, `puzzle_id`, `limit=20` |
| `get_approved_hint` | `session_id`, `team_id`, `puzzle_id`, `hint_strength` |
| `record_hint_delivery` | `session_id`, `team_id`, `puzzle_id`, `hint_strength`, `delivered_at`, `reason_codes`, `idempotency_key` |
| `request_game_master` | `session_id`, `team_id`, 선택 `puzzle_id`, `reason`, `summary`, `idempotency_key` |

### Edge Case

- 정의되지 않은 입력 필드는 `extra="forbid"`로 거부한다.
- 힌트 강도는 `WEAK`, `STRONG`만 허용한다.
- 다른 팀 세션과 현재 문제가 아닌 `puzzle_id`는 기존 Runtime 정책으로 거부한다.
- 동일 `idempotency_key`와 동일 payload 재요청은 기존 결과를 재사용한다.
- 고객 Agent에는 세션 생성·진도 변경·운영자 큐 관리 Tool을 등록하지 않는다.

## How

- `mcp_server/server.py`에 6개의 `@mcp.tool()` 함수를 명시한다.
- 기존 `mcp_server/tools/` 구현은 alias로 호출해 Runtime 비즈니스 로직을 중복 작성하지 않는다.
- `mcp_server/schemas.py`에 입력·출력 모델과 허용 Enum을 둔다.
- docstring에는 호출 조건, 입력, 반환, 부작용, 호출 금지를 모두 작성한다.
- 출력 모델에는 정답 필드를 정의하지 않는다.
- 현재 코드의 import 경로와 호환되도록 MCP Python SDK는 `mcp>=1.29,<2`로 고정한다.

## AC

### AC-01 명시 등록

GIVEN MCP 서버 모듈을 import했고
WHEN `tools/list`를 호출하면
THEN 핵심 Tool 6개만 반환되고 각 이름이 함수의 명시적 `@mcp.tool()` 등록과 일치한다.

### AC-02 엄격한 schema

GIVEN 등록된 Tool의 입력·출력 schema가 있고
WHEN 알 수 없는 필드를 입력하면
THEN Tool 본문 실행 전에 validation error로 거부된다.

### AC-03 힌트 강도 제한

GIVEN `get_approved_hint` 호출 입력이 있고
WHEN `NORMAL` 또는 임의 문자열을 전달하면
THEN `WEAK`·`STRONG` Enum 검증에서 거부된다.

### AC-04 쓰기 멱등성

GIVEN 동일한 힌트 기록 payload와 `idempotency_key`가 있고
WHEN `record_hint_delivery`를 두 번 호출하면
THEN 오류 없이 기존 결과를 재사용하고 새 이력을 중복 생성하지 않는다.

### AC-05 기존 회귀 방지

GIVEN 기존 백엔드 테스트와 신규 MCP 계약 테스트가 있고
WHEN 전체 테스트를 실행하면
THEN 모두 통과한다.
