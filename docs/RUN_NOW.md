# 로컬 실행 절차

## 사전 조건

- Docker Desktop이 실행 중이어야 한다.
- Python 3.12 이상과 Node.js 20 이상을 권장한다.
- 실제 API 호출을 하려면 `.env`에 사용할 Provider 키를 입력한다.
- 키가 없어도 baseline·일부 규칙 테스트는 실행할 수 있다.

## Backend, MCP와 DB

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- FastAPI 문서: http://localhost:8000/docs
- FastAPI Health check: http://localhost:8000/health
- MCP Streamable HTTP: http://localhost:8001/mcp
- Compose의 `api`와 `mcp`는 서로 다른 컨테이너이며 `http://mcp:8001/mcp`로 통신한다.
- 두 서비스는 같은 PostgreSQL 저장소를 사용한다. 별도 프로세스에서 메모리 저장소를 사용하면 세션이 공유되지 않으므로 Compose가 `RUNTIME_REPOSITORY=postgres`를 명시적으로 설정한다.

## Frontend

```powershell
Set-Location frontend
npm ci
npm run dev
```

- 고객 화면: http://localhost:5173/customer
- 게임마스터 화면: http://localhost:5173/game-master
  - Escape Ops 정적 데모가 표시되며 실시간 관제, 테마·퍼즐, 힌트 정책, 판정 로그, 연동 관리 화면을 시험할 수 있다.
  - Escape Ops 정적 화면은 데모 데이터를 유지하지만, 요청 큐 패널은 FastAPI 게임마스터 API에 연결되어 있다.

Frontend가 다른 API 주소를 사용해야 하면 `frontend/.env`의 `VITE_API_BASE_URL`을 설정한다.

## 실행 후 검증

```powershell
Invoke-WebRequest http://localhost:8000/health
Set-Location frontend
npm test -- --run
npm run build
```

Backend 테스트와 환경별 주의사항은 [TESTING.md](./TESTING.md)를 참고한다.

## Docker 없이 MCP Streamable HTTP 실행

Docker를 사용하지 않을 때는 아래처럼 MCP 서버와 FastAPI를 서로 다른 터미널에서 실행한다. 이 수동 방식에서 두 프로세스 간 세션을 공유하려면 외부 PostgreSQL을 사용해야 한다.

터미널 1:

```powershell
$env:MCP_SERVER_TRANSPORT = "streamable-http"
$env:MCP_SERVER_HOST = "127.0.0.1"
$env:MCP_SERVER_PORT = "8001"
python -m mcp_server.server
```

터미널 2:

```powershell
$env:MCP_CLIENT_TRANSPORT = "streamable-http"
$env:MCP_SERVER_URL = "http://127.0.0.1:8001/mcp"
$env:MCP_CLIENT_TIMEOUT_SECONDS = "10"
uvicorn backend.main:app --host 127.0.0.1 --port 8000
```

환경변수를 지정하지 않으면 기존 개발·단위 테스트 호환을 위해 등록된 FastMCP Tool을 같은 프로세스에서 호출한다. 이 경우에도 Tool schema와 서버 wrapper 검증은 거치지만 HTTP 소켓은 사용하지 않는다.
