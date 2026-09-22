# 수정 기획안 대조·보완·교차검증 보고서 — 2026-09-22

## 1. 기준 자료

이번 정렬은 다음 세 자료를 기준으로 했다.

1. `docs/01-operations-agent-problem-definition.md` — 이번에 올라온 수정 기획안
2. 기존 프로젝트 코드/문서 — 직전 교차검증본
3. 2차 프로젝트 가이드 및 기능별 개발가이드 — RAG/LangGraph 금지, FastAPI·MCP·평가/관측 경계 확인

임의 모델명·임의 우선순위 점수·임의 평가 정답·임의 도메인 데이터를 추가하지 않았다.

## 2. 이번에 바꾼 부분

| 영역 | 기존 상태 | 수정 기획안 기준 | 이번 반영 |
|---|---|---|---|
| 프로젝트 정의 | 힌트 판단 Agent 중심 | 고객 요청·힌트·장비 이상·GM 요청을 연결하는 운영 보조 Agent | README/Architecture/Status 문구 정렬 |
| GM 요청 최초 상태 | `PENDING` | `OPEN` | backend schema/runtime, frontend type/UI/test, 문서 모두 `OPEN`으로 정렬 |
| GM 요청 상태 변경 MCP | `update_master_request` 함수는 있으나 FastMCP 등록 누락 | 핵심 MCP 도구로 명시 | FastMCP 등록 목록에 추가 |
| 진도 변경 권한 | `mark_puzzle_solved`가 FastMCP와 public solve route에 노출 | 고객 Agent 직접 노출 금지 | FastMCP 등록 제거, public solve route 제거 |
| QR 입장 | create session이 `qr_payload` 반환, QR SVG route 존재 | MVP는 임시 `session_id`/`team_id`, QR 후속 | active API/Frontend contract/의존성에서 QR 제거 |
| 재요청 쿨다운 | 정적 GM 화면에 60초 표시 | 수정 기획안에는 고정 초 수 없음 | 60초를 제거하고 `미확정` 표시 |
| MCP 문서 | 핵심 목록에 GM 상태 변경 누락 | `get/update_master_request` 포함 | guide/route/spec 정렬 |
| 평가 문서 | 범용 템플릿 중심 | 승인 힌트, 미래 퍼즐, STRONG, ANSWER, 중복, MCP, 지연, LLM 오류 등 도메인 성공 기준 | `EVAL_REPORT.md`에 실측값 빈칸 상태로 추가 |
| 기획 원문 | repo 내 최신 기준 문서 없음 | 새 기획안이 현재 방향 | 원문을 `docs/01-operations-agent-problem-definition.md`로 그대로 보존 |

## 3. 현재 구현과 기획이 맞는 부분

| 기획 방향 | 현재 확인 | 상태 |
|---|---|---|
| RAG 금지 | runtime/source dependency scan에서 구현 흔적 없음 | 유지 |
| LangGraph 금지 | runtime/source dependency scan에서 구현 흔적 없음 | 유지 |
| LocalRuntime P0 | `LocalRuntime` + MemoryRepository 기본 | 구현 |
| LLM이 강도/정답 최종 결정 안 함 | IntentResult 구조화 후 `hint_decision.py`/AnswerVault가 결정 | 구현 |
| 승인 힌트만 사용 | `get_approved_hint` 실패 시 임의 힌트 생성 금지 | 구현 |
| ANSWER 동의 | `offer_id` + `/api/answers/confirm` | 구현 |
| 장비 이상/직원 호출 분기 | `EQUIPMENT_ISSUE`/`MASTER_REQUEST` → GM 요청 | 구현 |
| GM 요청 멱등성/상태 전이 | idempotency + OPEN/ACKNOWLEDGED/RESOLVED/CANCELED | 구현 |
| STT Adapter 경계 | `MockSTTAdapter` → 기존 Agent | 구현 골격 |
| ERCC 후속 | `ERCCAdapter` 미연결 placeholder | 후속 유지 |

## 4. 이번에 임의 구현하지 않은 미비점

| 미비점 | 현재 사실 | 왜 이번에 만들지 않았는가 | 필요한 다음 근거 |
|---|---|---|---|
| `GENERAL_INQUIRY` | IntentType에 없음 | 응답 상태·허용 데이터·평가 정답이 수정 기획안에 없음 | 팀이 일반 문의 계약/예시/정답 기준 확정 |
| LLM 최종 문장 생성 | 현재는 승인 힌트/코드 결과 직접 반환 | 두 번째 LLM 호출의 Pydantic 출력·실패/재시도·관측 계약이 없음 | response schema + 실패 정책 + 평가 기준 |
| 장비 이상 전용 이력 | 현재 GM request reason에 `EQUIPMENT_ISSUE:`로 남음 | 별도 event schema/필드/보존 정책이 없음 | EquipmentIssue schema와 저장 계약 |
| 실제 다중 방 현황 | GM 화면 일부가 정적 데모, 실제 요청 큐만 연결 | 전체 활성 세션 조회 계약이 없음 | Repository/MCP의 active session 조회 계약 |
| 자동 우선순위 | 없음 | 팀 승인 규칙/평가 정답 없음 | 우선순위 기준과 동일 평가셋 |
| 운영 요약/인수인계 | 없음 | 수정 기획안 05에서 후속 범위로 명시 | 원천 이벤트/출력 계약 |
| 테마별 통계/관리자 화면 | 없음 | 후속 범위이며 원천 데이터 계약 미확정 | 통계 정의, 관리자 권한 |
| 고객 외 직원 자연어 Agent | `/api/agent`는 고객 흐름 | 직원 입력 contract/권한 미정 | 역할/권한/endpoint 결정 |
| 진도 변경 API | active public route 제거 | 고객이 진도를 바꾸면 안 됨. GM/internal event 인증 계약도 아직 없음 | 내부 이벤트 또는 GM 전용 API contract |
| QR 입장 | active route/응답에서 제거 | 수정 기획안에서 후속 | 예약/티켓/인증 연동 기준 |
| 최종 STT Provider | 실험상 Large Epoch2 선정, 서비스는 Mock | Python 3.13 Gate 2 및 실제 WAV 통합 미검증 | Adapter load + 실제 전사 + dependency gate |
| 외부 LLM 핵심 실행 | baseline/OpenRouter 코드 존재 | 실제 API 호출 근거 없음 | 동일 eval 기준 실호출 기록 |
| Langfuse 실제 운영 | 코드 연결 준비 | 외부 trace/prompt/version 실측 없음 | trace + prompt version + rollback 증거 |
| 원격 `/mcp` | FastMCP source/tool contract 존재 | 이번 검증 환경에 `mcp` package가 없어 runtime import 불가, HTTP transport도 미배포 | 의존성 설치 환경에서 tool listing + transport test |
| PostgreSQL 실서버 | repository/schema 있음 | 외부 DB 실연결/재시작 보존 미검증 | 실제 DB 통합 테스트 |
| 평가 판정자/rubric/baseline | 30건/why는 있음 | 팀 판정자·최종 score rubric·baseline 결과 없음 | D4 팀 확정/실행 |
| injection 3건 | 확정 문항 없음 | 임의 공격 문항 생성 금지 | 팀 승인 평가 문항 3건 이상 |

## 5. 남겨 둔 후속 파일/타입

삭제는 하지 않았다. 따라서 다음은 **active runtime에는 연결되지 않지만 후속 참고용으로 남아 있다.**

- `backend/services/qr_service.py` — 현재 HTTP API에서 미사용
- `SolvePuzzleRequest` — 현재 public route에서 미사용
- `mark_puzzle_solved` Runtime/tool 함수 — 내부 진도 로직 테스트용, FastMCP 공개 등록 안 됨

후속 계약이 확정되기 전에는 이 파일/타입을 “현재 기능”으로 설명하지 않는다.

## 6. 교차검증 결과

| 검증 | 실제 결과 | 범위/한계 |
|---|---|---|
| Python compile | `python -m compileall -q backend mcp_server` PASS | Python 문법/컴파일 |
| Backend tests | `python -m pytest -q backend/tests` → **57 passed** | 외부 서비스 성공을 의미하지 않음 |
| FastAPI routes | OpenAPI 실제 route 확인 | solve/QR route 없음, session/agent/master/answer/voice route 존재 |
| GM 최초 상태 | LocalRuntime 실호출 → `OPEN` | MemoryRepository 기준 |
| MCP 공개 도구 source | `update_master_request` 등록, `mark_puzzle_solved` 미등록 확인 | source-level check |
| FastMCP runtime import | **미검증** | 현재 검증 컨테이너에 `mcp` package가 없어 `ModuleNotFoundError` |
| Escape Ops JS | `app.js`, `enhance.js` `node --check` PASS | 브라우저 E2E 아님 |
| Frontend Vitest | **미검증** | `node_modules` 없음 → `vitest: not found` |
| Docker Compose | **미검증** | 현재 검증 컨테이너에 Docker CLI 없음 |
| RAG/LangGraph | runtime/source import/dependency scan에서 구현 흔적 없음 | 문서 언급은 구현으로 보지 않음 |

## 7. 다음 작업 순서

1. D4에서 `GENERAL_INQUIRY`를 MVP에 넣을지 제외할지 결정하고, 넣는다면 응답 계약/평가 정답을 먼저 확정한다.
2. 30건 평가셋의 판정자·score rubric·baseline을 확정하고 같은 기준으로 측정한다.
3. injection 문항 3건 이상을 팀이 승인한다.
4. 실제 운영 현황을 만들려면 먼저 `active sessions` 조회 계약과 GM 우선순위 규칙을 문서로 확정한다.
5. 최종 STT Large Epoch2는 Python 3.13 Gate 2 통과 후 `MockSTTAdapter`를 교체한다.
6. Langfuse Prompt version/trace와 외부 LLM 실제 호출을 같은 평가셋으로 검증한다.
7. 원격 `/mcp`, PostgreSQL, Docker/Vercel/Cloud Run은 실제 실행 증거가 생긴 뒤 완료로 바꾼다.

## 8. 최종 판정

이번 수정본은 **수정 기획안에서 바로 확정 가능한 계약만 코드/문서에 반영**했다.

특히 `OPEN` 상태, GM 요청 update MCP, 고객 진도 변경 금지, QR 후속 범위는 실제 코드까지 정렬했다. 반대로 일반 문의, 운영 우선순위, 운영 요약/통계, 장비 전용 이력처럼 schema와 평가 기준이 없는 부분은 임의로 만들지 않고 미비점으로 남겼다.

## 9. 패키지 생성 후 2차 교차검증

작업 폴더 검증 뒤 ZIP을 생성하고, ZIP을 새 디렉터리에 다시 풀어 **패키지 자체를 기준으로 재검증**했다.

- `python -m compileall -q backend mcp_server` → PASS
- `python -m pytest -q backend/tests` → **57 passed**
- OpenAPI에서 QR route / 고객 solve route 없음 확인 → PASS
- LocalRuntime GM 요청 최초 상태 `OPEN` → PASS
- FastMCP source 등록 목록에 `update_master_request` 포함, `mark_puzzle_solved` 제외 → PASS
- Escape Ops `app.js`, `enhance.js` syntax → PASS
- runtime/source의 RAG/LangGraph import/dependency scan → PASS

Frontend Vitest, FastMCP runtime import, Docker Compose는 앞 절에 적은 환경 제한 때문에 여전히 미검증이다.
