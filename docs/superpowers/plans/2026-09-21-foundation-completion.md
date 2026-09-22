# Foundation Completion Implementation Plan

> **기록 주의(2026-09-22):** 이 파일은 2026-09-21 작성 당시의 구현 계획 기록이다. 현재 구현·검증 상태는 `docs/STATUS.md`와 `docs/FOUNDATION_GATE_2026-09-22.md`를 기준으로 확인한다. 이후 확정된 STT 모델 선정 등은 이 과거 계획 문구를 소급 수정하지 않는다.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 현재 구현된 Hint Agent 골격을 계약·실행환경·통합검증이 가능한 Foundation 완료 상태로 정리하고, 마지막에 기능별 개발 가이드를 작성한다.

**Architecture:** 고객/게임마스터 프론트엔드는 FastAPI API를 호출하고, FastAPI는 Agent Orchestrator와 로컬 MCP Tool 계층을 통해 상태를 조회·변경한다. P0는 MemoryRepository를 사용하며 PostgreSQL은 동일한 RuntimeRepository 계약의 선택형 어댑터로 검증한다. LLM/STT는 교체 가능한 경계로 유지하고 상태·진도·힌트 강도·동의·직원 호출은 코드와 MCP가 결정한다.

**Tech Stack:** React + TypeScript + Vite, FastAPI, Pydantic, FastMCP, Python pytest, Vitest, PostgreSQL 16, Docker Compose, Langfuse SDK.

**Spec:** `docs/specs/mcp-data-contract.md`, `docs/specs/frontend-backend-integration.md`, `docs/specs/repository-migration.md`, `docs/specs/stt-integration.md`

## Global Constraints

- RAG와 LangGraph는 사용하지 않는다.
- P0 기본 Runtime은 `memory`이며 PostgreSQL은 `RUNTIME_REPOSITORY=postgres`로 선택한다.
- WEAK와 STRONG은 정책 조건에 따라 자동 제공할 수 있고, ANSWER는 유효한 `offer_id`와 명시적 동의 없이는 반환하지 않는다.
- LLM은 의도·감정·문장 생성 및 도구 후보 제안만 담당한다.
- 세션 상태·진도·남은 시간·힌트 강도·정답 동의·게임마스터 호출은 코드/MCP가 결정한다.
- 실제 STT Provider 선정·학습·튜닝은 Foundation 이후 단계로 둔다.
- 변경 코드에는 정책·보안·상태 전이·예외 처리의 수정 사유를 주석 또는 docstring으로 남긴다.
- 기능 변경마다 해당 계약 테스트 또는 통합 테스트를 추가하고, 기존 동작을 unrelated refactor로 변경하지 않는다.

## Review Focus

- 계약 문서와 실제 응답 상태가 어긋나면 프런트가 잘못된 상태를 표시한다. `test_repository_contract.py`와 API 계약 테스트에서 성공·실패 상태를 함께 고정한다.
- `RUNTIME_REPOSITORY=postgres`가 설정됐지만 `DATABASE_URL`·드라이버·DB가 없으면 시작/첫 저장 시 원인을 알 수 있어야 한다. Repository 설정 테스트와 Docker smoke test에서 확인한다.
- 중복 요청이 재시작·동시 요청에서 이중 기록되지 않아야 한다. idempotency 계약 테스트와 PostgreSQL 통합 테스트에서 확인한다.
- 고객 요청과 게임마스터 요청에서 다른 팀의 세션을 조회·변경할 수 없어야 한다. API 권한 테스트에서 확인한다.
- STT 품질 부족·시간 초과·알 수 없는 명령은 힌트 제공이나 직원 호출로 임의 승격되지 않아야 한다. STT 실패 정책 테스트에서 확인한다.

---

### Task 1: Contract and status consistency

**Files:**
- Modify: `docs/specs/mcp-data-contract.md`
- Modify: `backend/schemas.py`
- Modify: `backend/routers/agent.py`, `backend/routers/answers.py`, `backend/routers/master.py`, `backend/routers/stt.py`
- Test: `backend/tests/test_access_policy.py`, `backend/tests/test_answer_confirmation_api.py`, `backend/tests/test_hint_failure_policy.py`

**Interfaces:**
- Consumes: `AgentResponse`, `AnswerConfirmationRequest`, `STTAgentResponse`, current MCP tool names.
- Produces: 문서와 API에서 일치하는 성공·실패 상태, ANSWER 동의 흐름, 권한 오류 응답.

- [ ] 문서의 STRONG 자동 제공과 ANSWER 동의 요구를 구분하고, 실패 상태를 `INSUFFICIENT_CONTEXT`, `OUT_OF_SCOPE`, `TOOL_FAILURE`로 매핑한다.
- [ ] 각 상태에 대해 현재 라우터가 반환하는 HTTP status와 Pydantic body를 테스트로 고정한다.
- [ ] 문서 체크리스트와 실제 코드의 이름·필드가 일치하는지 `rg`로 확인한다.
- [ ] Backend 전체 테스트를 실행해 44개 이상 기존 테스트가 유지되는지 확인한다.

### Task 2: LocalRuntime and PostgreSQL execution boundary

**Files:**
- Modify: `mcp_server/adapters/local_runtime.py`
- Modify: `backend/repositories/postgres.py`, `backend/db/schema.sql`
- Modify: `.env.example`, `docker-compose.yml`, `backend/requirements.txt`
- Test: `backend/tests/test_postgres_repository.py`, `backend/tests/test_repository_contract.py`

**Interfaces:**
- Consumes: `RuntimeRepository`, `RUNTIME_REPOSITORY`, `DATABASE_URL`.
- Produces: memory 기본 실행과 PostgreSQL 선택 실행의 동일한 Repository 계약.

- [ ] Memory 모드에서 외부 DB 없이 세션·힌트·멱등성·게임마스터 요청이 동작하는지 유지한다.
- [ ] PostgreSQL 모드에서 schema 적용, 세션 저장/조회, 힌트 이력, 멱등성, 게임마스터 요청 CRUD를 실제 DB에서 검증한다.
- [ ] Docker Compose에서 API가 `RUNTIME_REPOSITORY=postgres`로 시작할 수 있도록 `.env.example`과 compose 설명을 맞춘다.
- [ ] 실제 DB가 없는 환경에서는 연결 검증을 성공으로 보고하지 않고, 미검증 범위를 기록한다.

### Task 3: FastAPI and MCP integration smoke flow

**Files:**
- Modify: `backend/main.py`, `backend/services/mcp_client.py`, `mcp_server/server.py`
- Modify: `mcp_server/tools/session_tools.py`, `mcp_server/tools/puzzle_tools.py`, `mcp_server/tools/hint_tools.py`, `mcp_server/tools/event_tools.py`, `mcp_server/tools/master_tools.py`
- Test: `backend/tests/test_repository_contract.py`, new `backend/tests/test_api_smoke.py`

**Interfaces:**
- Consumes: FastAPI routes and local FastMCP tool functions.
- Produces: 세션 생성 → 힌트 요청 → 힌트 이력 저장 → 게임마스터 요청의 단일 smoke flow.

- [ ] `/health`, `/api/themes`, `/api/sessions`, `/api/agent`, `/api/answers/confirm`, `/api/agent/voice`, `/api/master/requests`의 최소 호출 순서를 테스트한다.
- [ ] 각 요청의 session/team 경계를 서버가 재계산하는지 확인한다.
- [ ] 도구 실패가 API에서 정의된 실패 상태로 변환되는지 고정한다.
- [ ] 별도 네트워크 MCP transport는 P0 범위로 확장하지 않고, 현재 로컬 호출 경계를 문서와 테스트에 명시한다.

### Task 4: Customer and game-master UI skeleton integration

**Files:**
- Modify: `frontend/src/api.ts`, `frontend/src/App.tsx`, `frontend/src/styles.css`
- Modify: `frontend/src/api.test.ts`, `frontend/src/app.test.tsx`
- Check: `docs/specs/frontend-backend-integration.md`

**Interfaces:**
- Consumes: FastAPI endpoint contracts and response status values.
- Produces: 고객 세션/힌트/정답 동의/음성 입력과 게임마스터 큐의 최소 동작 UI.

- [ ] API 성공·실패·네트워크 오류를 고객 화면에 구분 표시한다.
- [ ] ANSWER 동의 전에는 정답 텍스트를 렌더링하지 않는 UI 테스트를 추가한다.
- [ ] 게임마스터 큐의 polling과 상태 변경 버튼이 정의된 전이만 요청하는지 테스트한다.
- [ ] `npm test -- --run`과 `npm run build`를 실행한다.

### Task 5: Provider and observability boundaries

**Files:**
- Modify: `backend/services/llm.py`, `backend/services/stt.py`, `backend/services/langfuse_service.py`
- Modify: `.env.example`, `docs/specs/stt-integration.md`, `docs/specs/observability.md`
- Test: `backend/tests/test_stt_pipeline.py`, `backend/tests/test_langfuse_observation.py`

**Interfaces:**
- Consumes: baseline LLM, Mock STT Adapter, Langfuse observation allowlist.
- Produces: provider 교체 지점과 민감정보 마스킹이 유지되는 관측 경계.

- [ ] baseline은 API key 없이 동작하고 외부 Provider 실패 시 코드 기반 실패 정책으로 내려간다.
- [ ] STT는 Mock Adapter를 유지하되 품질·timeout·빈 전사문 정책을 고정한다.
- [ ] Langfuse observation에 hint_text, answer, transcript, offer_id가 기록되지 않는지 테스트한다.
- [ ] 실제 Provider 연결·모델 선정·튜닝은 후속 작업으로 명시한다.

### Task 6: Evaluation and deployment readiness

**Files:**
- Modify: `evals/dataset.jsonl`, `evals/README.md`, `docs/TESTING.md`, `docs/DEPLOYMENT.md`, `docs/RUN_NOW.md`
- Modify: `Dockerfile`, `docker-compose.yml`
- Test: new `tests/integration/test_p0_flow.py`, optional `tests/e2e/README.md`

**Interfaces:**
- Consumes: finalized API/MCP contracts and current local runtime.
- Produces: P0 실행 명령, 평가 데이터 구조, Docker smoke 검증 절차.

- [ ] 정상 힌트, STRONG 자동 제공, ANSWER 동의, 장비 이상, 다른 팀 접근 거부를 포함한 최소 평가셋을 고정한다.
- [ ] Dockerfile이 backend, mcp_server, skills와 의존성을 포함하는지 빌드 검사한다.
- [ ] `.env` 없는 환경에서 compose 검증을 성공으로 보고하지 않고 필요한 설정을 안내한다.
- [ ] Vercel frontend와 Dockerized backend의 환경변수 경계를 문서화한다.

### Task 7: Feature development guides

**Files:**
- Create: `docs/guides/00-development-principles.md`
- Create: `docs/guides/01-session-management.md`
- Create: `docs/guides/02-stt-input.md`
- Create: `docs/guides/03-hint-policy.md`
- Create: `docs/guides/04-answer-confirmation.md`
- Create: `docs/guides/05-game-master-request.md`
- Create: `docs/guides/06-mcp-tools.md`
- Create: `docs/guides/07-postgresql-runtime.md`
- Create: `docs/guides/08-llm-provider.md`
- Create: `docs/guides/09-frontend.md`
- Create: `docs/guides/10-deployment-and-evaluation.md`
- Modify: `README.md`, `docs/STATUS.md`, `docs/INTEGRATION_MAP.md`

**Interfaces:**
- Consumes: verified code, tests, contracts, and deployment notes from Tasks 1–6.
- Produces: 팀원이 기능별로 목표·입출력·LLM/코드 역할·실패처리·테스트·확장점을 따라 구현할 수 있는 가이드.

- [ ] 각 가이드는 목표, 사용자 시나리오, schema, API/MCP, LLM 역할, 코드 역할, 실패 상태, 신뢰 경계, 테스트, 현재 상태, 다음 확장 단계를 포함한다.
- [ ] 검증되지 않은 외부 연결은 “미검증”으로 표시하고 성공처럼 서술하지 않는다.
- [ ] RAG/LangGraph 금지, STT Provider 후속, QR/ERCC/Escapp 후속 결정을 공통 가이드에 반영한다.
- [ ] README에서 Foundation 완료 범위와 기능별 가이드 진입점을 연결한다.
- [ ] 최종 backend/frontend/build/compile/diff 검사를 다시 실행한다.

## Self-review result

- Spec coverage: 계약, Runtime, MCP/FastAPI, UI, STT/LLM/Langfuse, Docker/eval, 기능별 문서를 각각 Task 1–7에 배치했다.
- Placeholder scan: 작업 범위를 임의의 “나중에 구현”으로 남기지 않고, 후속인 Provider·ERCC·QR은 현재 프로젝트 결정으로 명시했다.
- Type consistency: 기존 `RuntimeRepository`, `AgentResponse`, `AnswerConfirmationRequest`, `STTAgentResponse`와 현재 라우터 경계를 기준으로 작성했다.
- Review focus: 계약 상태, DB 설정, 멱등성, 권한, STT 오류를 각 Task의 테스트 항목에 연결했다.
