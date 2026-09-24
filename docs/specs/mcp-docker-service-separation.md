# MCP Docker 서비스 분리

## Why

현재 Docker Compose는 FastAPI만 실행하며 MCP 서버는 별도 프로세스로 기동하지 않는다. Streamable HTTP client가 구현되어도 배포 구성에서 MCP 주소가 없기 때문에 실제 서비스 간 호출 증거를 만들 수 없다. 또한 API와 MCP를 단순히 메모리 모드로 분리하면 각 프로세스가 서로 다른 세션 저장소를 가져 API가 생성한 세션을 MCP가 조회하지 못한다.

## Goal

- `docker compose up --build` 한 번으로 `api`, `mcp`, `db` 3개 서비스를 기동한다.
- API는 `http://mcp:8001/mcp`로 핵심 MCP Tool을 호출한다.
- API와 MCP는 같은 PostgreSQL 저장소를 사용해 세션·힌트 이력·게임마스터 요청을 공유한다.
- DB와 MCP healthcheck가 준비된 뒤 API가 시작되도록 의존성을 설정한다.
- Compose 설정 검증과 API→MCP 환경 계약 테스트를 추가한다.

Out of Scope:

- 운영 배포 플랫폼과 TLS·OAuth
- PostgreSQL 연결 풀·migration 도구·secret manager
- MCP 다중 replica와 장기 연결 최적화
- 프론트엔드 컨테이너화
- 기존 STRONG·ANSWER 정책 충돌 수정

## What

### Happy Path

1. Compose가 PostgreSQL을 시작하고 healthcheck를 통과한다.
2. MCP 서비스가 Streamable HTTP를 `0.0.0.0:8001`에서 연다.
3. API 서비스가 `MCP_CLIENT_TRANSPORT=streamable-http`와 내부 DNS 주소를 사용해 시작한다.
4. API가 PostgreSQL에 세션을 생성한다.
5. MCP가 같은 PostgreSQL에서 해당 세션을 읽고 현재 문제의 승인 힌트를 반환한다.

### Edge Case

- 로컬 `.env`가 없어도 baseline 설정으로 Compose 구성을 해석할 수 있어야 한다.
- DB가 준비되지 않으면 MCP와 API를 준비 완료로 간주하지 않는다.
- MCP가 준비되지 않으면 API가 먼저 시작해 연결 실패를 반복하지 않는다.
- 호스트의 8001 포트는 개발 확인용으로만 공개하고 서비스 간 호출은 `mcp:8001`을 사용한다.
- 각 컨테이너에서 `RUNTIME_REPOSITORY=memory`로 덮어쓰지 못하도록 Compose가 `postgres`를 명시한다.

## How

- 하나의 Docker image를 사용하고 서비스별 `command`만 분리한다.
- `api` command는 `uvicorn backend.main:app --host 0.0.0.0 --port 8000`이다.
- `mcp` command는 `python -m mcp_server.server`이며 MCP 환경변수로 Streamable HTTP를 선택한다.
- `api`와 `mcp` 모두 `RUNTIME_REPOSITORY=postgres` 및 동일한 `DATABASE_URL`을 사용한다.
- `db`는 `pg_isready`, `mcp`는 로컬 TCP 연결로 healthcheck한다.
- `.dockerignore`에서 `.env`, Git metadata, 가상환경, cache와 빌드 산출물을 제외한다.
- 테스트는 Compose YAML 텍스트의 필수 서비스·환경·의존성 계약을 검사한다.

## AC

### AC-01 서비스 분리

GIVEN Docker Compose 설정이 있고
WHEN 서비스 목록을 검사하면
THEN `api`, `mcp`, `db`가 각각 별도 서비스로 정의된다.

### AC-02 실제 MCP 주소

GIVEN API 컨테이너 환경이 있고
WHEN MCP client 설정을 검사하면
THEN transport는 `streamable-http`이고 URL은 `http://mcp:8001/mcp`이다.

### AC-03 공유 저장소

GIVEN API와 MCP가 별도 프로세스로 실행되고
WHEN 각 서비스의 Runtime 설정을 검사하면
THEN 두 서비스 모두 같은 PostgreSQL URL과 `RUNTIME_REPOSITORY=postgres`를 사용한다.

### AC-04 준비 순서

GIVEN DB와 MCP가 아직 준비되지 않았고
WHEN Compose가 서비스를 시작하면
THEN healthcheck 성공 전에는 의존 서비스가 준비된 것으로 처리되지 않는다.

### AC-05 검증

GIVEN Docker daemon을 사용할 수 있는 환경이 있고
WHEN `docker compose up --build` 후 API Agent 요청을 실행하면
THEN API가 별도 MCP 컨테이너를 통해 승인 힌트를 반환한다.

Docker daemon을 사용할 수 없는 환경에서는 Compose config·계약 테스트·Python 회귀 테스트까지만 검증하고 실제 컨테이너 왕복은 미검증으로 보고한다.
