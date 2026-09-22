# 로컬 실행 절차

## 사전 조건

- Docker Desktop이 실행 중이어야 한다.
- Python 3.12 이상과 Node.js 20 이상을 권장한다.
- 실제 API 호출을 하려면 `.env`에 사용할 Provider 키를 입력한다.
- 키가 없어도 baseline·일부 규칙 테스트는 실행할 수 있다.

## Backend와 DB

```powershell
Copy-Item .env.example .env
docker compose up --build
```

- FastAPI 문서: http://localhost:8000/docs
- Health check: http://localhost:8000/health
- Docker Compose의 Postgres는 준비되어 있지만, 현재 P0 기본 LocalRuntime은 메모리 저장소를 사용한다. PostgreSQL 검증 시 `.env`의 `RUNTIME_REPOSITORY=postgres`를 명시한다.

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
