# Testing Guide

## 검증 범위

| 대상 | 명령 | 목적 |
|---|---|---|
| Backend 문법 | `py -3 -m compileall -q backend mcp_server` | import 전 문법 오류 확인 |
| Backend 단위 테스트 | `py -3 -m pytest backend/tests -q` | Pydantic·힌트 정책·라우팅 테스트 |
| ANSWER 계약 테스트 | `py -3 -m unittest backend.tests.test_api_contract -v` | Agent 응답과 AnswerVault 응답 분리 확인 |
| ANSWER API 통합 테스트 | `py -3 -m unittest backend.tests.test_api_integration -v` | `/api/agent` → `/api/answers/confirm` HTTP 흐름 |
| STT 경계 테스트 | `py -3 -m pytest backend/tests -q` | STT 실패·빈 전사 시 판정 미실행 계약 확인 |
| Frontend 테스트 | `Set-Location frontend; npm test -- --run` | React UI 동작 확인 |
| Frontend build | `Set-Location frontend; npm run build` | TypeScript·Vite production build 확인 |
| API smoke test | `Invoke-WebRequest http://localhost:8000/health` | 서버 기동 확인 |

## Windows 환경 준비

```powershell
py -3 -m venv .venv
.\.venv\Scripts\Activate.ps1
py -3 -m pip install -r backend/requirements.txt -r backend/requirements-dev.txt
```

Backend 테스트가 실패하면 먼저 현재 PowerShell의 Python과 패키지 설치 위치를 확인합니다.

```powershell
py -3 -c "import sys; print(sys.executable)"
py -3 -c "import fastapi, pytest; print(fastapi.__version__)"
```

`test_api_integration.py`는 FastAPI가 없는 최소 런타임에서는 자동으로 skip된다. 실제 HTTP 검증을
수행하려면 위 가상환경을 활성화한 뒤 `backend/requirements-dev.txt`까지 설치해야 한다.

## ANSWER API 계약

1. `POST /api/agent`에 정답 요청을 보내면 `ANSWER_CONFIRMATION_REQUIRED`와 `offer_id`를 반환한다.
2. 첫 응답에는 `answer` 필드가 없어야 한다.
3. `POST /api/answers/confirm`은 같은 세션·팀·퍼즐의 유효한 `offer_id`만 처리한다.
4. 성공 후 동일 토큰을 재사용하면 `403`을 반환해야 한다.
5. 현재 `GET /api/answers/reveal`은 제공하지 않으며, ANSWER 자동 공개 feature flag도 비활성이다.

## 통합 테스트 우선순위

1. 세션 생성 → 현재 세션 조회
2. 같은 `session_id`와 `team_id`에서 힌트 이력 공유
3. 다른 팀이 세션을 조회하거나 직원 호출을 시도할 때 거부
4. 현재 순서보다 미래인 퍼즐의 힌트 차단
5. 장비 이상·직원 직접 요청이 게임마스터 큐로 기록
6. 힌트 제공 후 진도 갱신
7. Docker Compose 기동 후 `/health` 확인

현재 환경에 Docker Desktop 또는 PostgreSQL 서버가 없으면 7번과 PostgreSQL Repository
실연결은 미검증으로 기록한다. `backend/tests/test_api_smoke.py`는 외부 DB 없이도
P0 FastAPI→MCP(LocalRuntime) 흐름을 검증한다.

## 검증 결과 기록 규칙

`EVAL_REPORT.md`에 실행 일시, Git SHA, 평가셋 건수, Provider, 모델, 실행 명령과 결과를 함께 기록합니다. “코드에 구현되어 있음”과 “현재 환경에서 테스트 통과”를 같은 의미로 쓰지 않습니다.
