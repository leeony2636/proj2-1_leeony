# Current Status

> 문서 기준: 2026-09-22. “구현됨”과 “외부 환경에서 검증됨”을 구분한다.

## 코드상 구현된 범위
- FastAPI `/health`, `/api/themes`, `/api/sessions`, `/api/agent`
- Vite 고객 화면 `/customer` 및 Escape Ops 게임마스터 관제 화면 `/game-master` (Vercel 배포 대상)
- `/game-master` Escape Ops 화면은 현재 대부분 정적 데모이며, 게임마스터 요청 큐는 실제 API와 5초 polling·상태 변경이 연결됨
- 가상 테마 2개: 교수님의 연구실(12), 마지막 열차(13)
- 각 퍼즐의 WEAK/NORMAL/STRONG 승인 힌트와 AnswerVault 분리
- baseline 기본 실행 및 OpenRouter 선택 연결 코드
- Azure OpenAI 1순위 후보를 위한 환경 변수 자리와 확장 경계
- LLM이 intent/emotion 및 필요한 MCP Tool 후보를 구조화
- 텍스트 입력 기준 Agent 흐름과 STT Adapter 경계 문서화. STT 실험상 Large-v3-Turbo + Escape-room Adapter Epoch 2를 선정했지만 실제 Provider 연결은 미완료
- 코드 기반 15분 + 남은 문제 50% STRONG 규칙
- 장비 이상/직원 직접 호출 → 게임마스터 큐
- 게임마스터 요청 큐 상태 전이(OPEN/ACKNOWLEDGED/RESOLVED/CANCELED)
- 게임마스터 요청 생성 시 세션 존재·팀 일치·담당자 식별자 최소 검증
- Mock STT Adapter와 `/api/agent/voice` 전사→Agent 입력 연결
- 게임마스터 요청 큐 React 패널과 5초 polling·상태 변경 연결
- Langfuse ObservationEvent allowlist·마스킹·환경변수 기반 SDK 연결
- RuntimeRepository 계약·MemoryRepository 분리 및 LocalRuntime 주입 경계
- PostgresRepository 1차 구현·schema.sql·환경변수 기반 Memory/PostgreSQL 선택
- 기능별 개발 가이드 11종과 README 진입점
- 퍼즐 해결 Runtime 기능은 내부에 유지하되 고객 HTTP/MCP 공개 경로에서는 제외
- MCP Tool Server 코드 (`update_master_request` 포함, `mark_puzzle_solved` 공개 등록 제외)


## 수정 기획안 재정렬 — 2026-09-22

기준 문서: `docs/01-operations-agent-problem-definition.md`

### 이번에 실제 반영한 것

- 프로젝트 정의를 “힌트 판단 Agent”에서 **고객 요청·힌트·장비 이상·게임마스터 요청을 연결하는 운영 보조 Agent**로 문서상 정렬
- 게임마스터 요청 최초 상태를 `OPEN`으로 통일
- `update_master_request`를 FastMCP 공개 도구에 추가
- `mark_puzzle_solved`는 Runtime 내부 기능으로 유지하되 FastMCP 공개 도구에서 제외
- 고객 공개 `POST /api/sessions/{session_id}/solve` 제거
- MVP의 QR 입장/QR SVG 경로와 `qr_payload` 응답 제거
- 재요청 60초처럼 팀 확정 근거가 없는 정적 UI 임의 수치 제거
- revised plan의 성공 기준을 `EVAL_REPORT.md`에 실측값 빈칸 상태로 추가

### 기획에는 있으나 임의 구현하지 않은 것

- `GENERAL_INQUIRY`: enum/응답 상태/판정 기준이 없어 미구현
- 승인 결과를 LLM이 사용자 친화적 문장으로 재생성하는 2차 호출: 입력/출력 계약과 실패 정책이 없어 미구현
- 장비 이상 전용 장애 이력: 저장 schema가 없어 현재는 게임마스터 요청 reason으로만 기록
- 실제 여러 방 운영 현황/우선순위 자동 판정: 전체 세션 조회 계약과 팀 승인 우선순위 규칙이 없어 미구현
- 게임 종료 운영 요약·테마별 통계·관리자 기능: 수정 기획안의 후속 확장 범위로 유지

## 현재 로컬·정적 검증 결과

### 2026-09-22 이번 교차 점검에서 직접 재검증

- Backend Python `compileall`: **PASS**
- Backend pytest: **57 tests passed**
- 생성 ZIP을 별도 디렉터리에 재추출한 뒤 Backend compile/pytest/OpenAPI/GM OPEN/MCP source registration/JS syntax/RAG·LangGraph scan을 다시 확인했고 동일하게 PASS
- FastAPI OpenAPI 실제 route 목록 확인: `/health`, `/api/themes`, `/api/sessions`, `/api/agent`, `/api/agent/voice`, `/api/answers/confirm`, 게임마스터 요청 상태 전이 route 포함. 수정 기획안에서 후속인 QR/고객 solve route는 없음
- Escape Ops `frontend/public/escape-ops/app.js`: `node --check` **PASS**
- Escape Ops `frontend/public/escape-ops/enhance.js`: `node --check` **PASS**
- FastMCP runtime import: **이번 검증 컨테이너에서는 미검증** (`mcp` package 부재). source 등록 목록은 `update_master_request` 포함 / `mark_puzzle_solved` 제외 확인
- 런타임 소스(`backend`, `mcp_server`, `frontend/src`, `skills`)에서 `langgraph`/RAG 구현 import·패키지 사용 흔적: **확인되지 않음**
- 평가셋: **30건**(normal 10 / boundary 12 / failure 8), 모든 문항에 `why` 존재, `adjudicator` 필드는 없음

### 현재 스냅샷에서 재검증하지 못한 항목

- Frontend Vitest / production build: 추출된 스냅샷에 `node_modules`가 없어 `npm test -- --run` 실행 시 `vitest: not found`. **이번 교차 점검에서는 PASS로 재확인하지 못함**
- 기존 저장소 문서에 과거 Frontend 테스트/빌드 성공 기록이 있었더라도, 이번 수정본 검증 결과와는 구분한다.

## 아직 실제 외부 실행 결과가 없는 항목
- 정적 Escape Ops 내부의 모든 데모 데이터 실데이터 교체
- 사용자의 OpenRouter API Key로 실제 `openrouter/free` 호출 성공 여부
- 실제 STT Provider 연결·소음 환경 인식률 검증
- Langfuse 실제 trace 전송 확인(코드는 연결 준비 완료, 외부 프로젝트 검증은 미완료)
- 실제 PostgreSQL 서버 연결·테이블 생성·재시작 후 데이터 보존
- PostgreSQL migration·rollback·연결 풀·다중 인스턴스 검증
- Backend가 별도 MCP transport를 통해 서버를 호출하는 네트워크 연결 (현재는 같은 Tool 함수를 로컬 호출)
- GCP Vertex / Azure Foundry Provider 실제 연결
- 최종 평가셋 30건과 100회 계약 테스트
- ERCC/Escapp 실제 연동

## 현재 데모 데이터 주의
두 가상 테마의 퍼즐/힌트/정답 내용은 서비스 흐름 시험을 위한 합성 시연 데이터입니다.
도메인 담당자가 실제 시연용 Ground Truth를 확정하기 전까지 평가 결과의 정답 근거로 사용하지 않습니다.

## 2026-09-22 Foundation 교차 점검

- Pydantic schema의 중복 `offer_id`/`offer_expires_at`/`requires_confirmation` 정의를 제거했다.
- 남은 문제 비율 50% 경계를 `>= 0.5`로 현재 Skill/Guide/Eval과 일치시켰다.
- 일반 STRONG 자동 제공과 정답 직접 요구 동의 흐름을 분리해 현재 Agent spec/test와 일치시켰다.
- 재요청 오버라이드 시간은 자료 간 60초/120초 충돌이 있어 구현을 추가하지 않았다.
- Langfuse Prompt Management/version 연결, 원격 `/mcp`, 실제 PostgreSQL, 최종 STT Gate 2, GM 운영 우선순위 규칙은 미완료다.
- D4 평가셋은 30건(정상10/경계12/실패8)이나 판정자 이름, score rubric, baseline 결과, injection 3건은 아직 확정되지 않았다.

상세는 `docs/FOUNDATION_GATE_2026-09-22.md`를 기준으로 한다.
