# Foundation Gate — 2026-09-22

## 현재 위치

일정 기준 오늘은 **D3(출력 계약·관측 규칙)** 단계다. D4(평가셋 30건 확정)는 2026-09-23 작업이므로, 현재 저장소에서 실제로 확인된 것과 아직 팀 결정이 필요한 것을 분리한다.

## 고정 방향

- 고객 발화/음성 → STT → LLM 구조화 → 코드 판정 → MCP 승인 데이터 조회/기록 → FastAPI 응답 → 화면
- LLM은 의도·감정·도구 후보를 구조화하며 WEAK/STRONG과 최종 정답을 결정하지 않는다.
- RAG와 LangGraph는 사용하지 않는다.
- 카메라/CCTV를 새 입력으로 추가하지 않는다.
- `/api/agent`와 MCP 도구 경계를 섞지 않는다. 현재 `/mcp` 원격 transport는 아직 배포 검증되지 않았다.
- 게임마스터 운영 보조는 실제 SessionState/힌트 이력/운영 요청 데이터를 근거로 해야 하며 정적 데모 값을 판정 데이터로 사용하지 않는다.

## D3 체크

| 요구 | 저장소에서 확인된 사실 | 판정 | 안 된 이유 / 다음 결정 |
|---|---|---|---|
| 입출력 Pydantic 스키마 | `AgentRequest`, `AgentResponse`, `STTResult`, `STTAgentResponse`, 정답/세션 요청 스키마 존재 | 부분 완료 | LLM Provider의 외부 structured output을 Pydantic 직접 강제하는 단계는 미구현 |
| 성공/실패 상태 | `NEED_MORE_INFO`, `PROVIDE_HINT`, `ANSWER_CONFIRMATION_REQUIRED`, `MASTER_REQUEST`, `CLOSED`, `ERROR` 존재 | 부분 완료 | 범위 밖/권한/도구 실패를 하나의 공통 failure code 체계로 묶는 결정은 없음 |
| 실패 경로 | 승인 힌트 누락→GM, timeout/connection 1회 재시도 후 ERROR, STT 낮은 품질→재입력 | 구현 확인 | OpenRouter의 broad exception fallback은 실패 유형별 분류가 아직 약함 |
| Langfuse observation 속성 | allowlist DTO와 민감정보 제외 규칙 존재 | 코드 완료 / 외부 미검증 | 실제 Langfuse trace 전송 확인 필요 |
| 프롬프트 버전 규칙 | `SYSTEM_PROMPT`는 코드 문자열 | 미완료 | Langfuse Prompt 이름/버전/rollback 규칙 팀 합의 및 연결 필요 |
| 신뢰 경계 1장 | `docs/TRUST_BOUNDARY.md` 추가 | 문서 완료 | injection 3건 이상 실측은 D4 이후 필요 |
| API endpoint 목록 | `docs/VERIFY_ROUTES.md`에 실제 FastAPI route와 MCP 경계 정리 | 문서 완료 | Streamable HTTP `/mcp`는 미검증 |
| 도메인 지식 출처 | `docs/DOMAIN_SOURCE_REGISTRY.md`에 현재 확인 가능한 출처와 미확인 권한 기록 | 부분 완료 | 사람 지식 담당자, 힌트 승인자, 외부 API 라이선스가 저장소에 없음 |

## D4 사전 점검

| 요구 | 현재 사실 | 판정 | 남은 것 |
|---|---|---|---|
| 평가셋 30건 | `evals/dataset.jsonl` 정확히 30건 | 완료 | 없음 |
| 정상/경계/실패 혼합 | 정상 10 / 경계 12 / 실패 8 | 완료 | 없음 |
| 문항별 판정 근거 | 모든 문항에 `why` 존재 | 완료 | 없음 |
| 문항별 판정자 이름 | 필드 없음 | 미완료 | 팀이 실제 판정자 지정 필요 |
| 경계 문항 도메인 판정 | 힌트 강도, 진행, 장비, 스포일러, 정답 노출 등 도메인 케이스 존재 | 부분 완료 | 팀 판정자 확인 전 최종 확정이라고 부르지 않음 |
| score rubric | `EVAL_REPORT.md` 템플릿만 있고 최종 수식/집계 미기입 | 미완료 | 팀 합의 필요 |
| baseline 기록 | 현재 저장소에는 30건 baseline 실행 결과 파일 없음 | 미완료 | 동일 프롬프트/입력/판정 기준으로 1차 측정 필요 |
| injection 3건 이상 | 역할 주장/정답 우회는 있으나 외부 도구 데이터 주입 3건은 확인되지 않음 | 미완료 | 임의 문항 추가 금지, 팀이 D4에서 확정 |
| 연휴 전 결정 잠금 | 문서화된 lock 목록 없음 | 미완료 | 9/23 팀 합의 필요 |

## 현재 코드에서 확인된 충돌/미비

| 항목 | 확인 내용 | 이번 반영 |
|---|---|---|
| 50% 경계 | Skill/Guide/Eval은 남은 문제 비율 `>= 0.5`, 기존 코드는 해결 비율 `< 0.5`라 정확히 50%에서 달랐음 | 코드와 테스트를 `remaining_puzzle_ratio >= 0.5`로 정렬 |
| STRONG/정답 동의 | 일반 STRONG 자동 제공 테스트/Agent spec과 기존 orchestrator가 충돌 | 일반 STRONG은 `PROVIDE_HINT`, 정답 직접 요구만 `ANSWER_CONFIRMATION_REQUIRED`로 정렬 |
| Answer confirm 테스트 | 현재 schema/router/function은 session/team/puzzle/offer 순서인데 한 테스트가 옛 호출 순서를 사용 | 테스트만 현재 계약으로 수정 |
| 재요청 오버라이드 | Skill/Eval에는 존재하지만 threshold가 eval 60초 vs 기존 spec 초안 120초로 충돌 | **코드 추가 안 함**. 팀 결정 필요 |
| offer TTL | 현재 코드 10분, 문서 초안 일부는 5분 | **값 변경 안 함**. 팀 결정 필요 |
| reason code 명칭 | eval dataset과 현재 `hint_decision.py` 명칭이 다름 | **변경 안 함**. 평가 계약에서 이름을 먼저 확정해야 함 |
| `/mcp` delivery | FastMCP tool 등록 코드는 있으나 Docker/FastAPI에서 `/mcp` transport 실행 근거 없음 | **임의 구현 안 함**. 사용 라이브러리 버전/배포 방식 확인 필요 |
| GM 운영 코파일럿 | SessionState/힌트 이력/GM 요청 데이터는 있으나 전체 세션 조회와 우선순위 규칙 없음 | **새 점수/데이터 생성 안 함**. UI 방향만 문서화 |

## STT 반영

- 실험상 선정: `openai/whisper-large-v3-turbo + Escape-room Adapter / Epoch 2`
- 동일 고정30에서 Small Epoch1 대비 Large Epoch2: WER 20.00%→6.15%, CER 3.17%→1.36%, Exact Match 14/30→23/30
- 서비스 코드: 여전히 `MockSTTAdapter`
- Python 3.13 Compatibility Gate 1은 Whisper Small Base CUDA load까지 PASS
- 최종 Large Epoch2 + PEFT Adapter의 Python 3.13 실제 WAV 전사는 아직 미검증

근거 파일은 `docs/stt/`에 보관한다.

## 게임마스터 운영 보조 방향

현재 구현으로 확실히 사용할 수 있는 신호는 세션의 시작시간/지속시간/진도, 같은 퍼즐의 힌트 이력, 게임마스터 요청 상태다. 이 데이터로 "현황을 보여주는 것"은 방향상 가능하지만, "어느 방을 먼저 봐야 하는지"를 자동 판정하려면 팀이 우선순위 규칙과 평가 정답을 먼저 확정해야 한다. 따라서 위험도 점수나 임의 알림 기준은 이번 반영에 추가하지 않았다.


## 수정 후 교차 검증 결과

| 검증 | 실제 결과 | 범위/한계 |
|---|---|---|
| Backend 문법 검사 | `python -m compileall -q backend mcp_server` PASS | Python 소스 문법/컴파일 범위 |
| Backend 테스트 | `python -m pytest -q backend/tests` → **57 passed** | 현재 로컬 Memory 중심 테스트 포함. 외부 서비스 성공을 의미하지 않음 |
| FastAPI route | OpenAPI에서 현재 route 목록 직접 확인 | `/mcp` Streamable HTTP endpoint는 없음 |
| Escape Ops JS | `app.js`, `enhance.js` 각각 `node --check` PASS | 문법 검사이며 브라우저 E2E는 아님 |
| RAG/LangGraph 금지 | 런타임 소스 경로에서 구현 import·패키지 사용 흔적 없음 | 문서에서 개념을 언급하는 것은 금지 구현과 구분 |
| 평가셋 구조 | 30건 = normal 10 / boundary 12 / failure 8, 전 문항 `why` 존재 | 판정자 이름·최종 rubric·baseline·외부 도구 데이터 injection 3건은 미확정 |
| Frontend 테스트/빌드 | **이번 스냅샷에서는 재검증 못함** | `node_modules` 부재로 `vitest: not found`; 의존성 설치 후 재실행 필요 |
| 외부 서비스 | **미검증** | Langfuse 실제 전송, OpenRouter 실호출, PostgreSQL 실서버, Cloud Run/Vercel, 원격 `/mcp`, 최종 STT Gate 2는 실행하지 않음 |

### 마지막 누락/충돌 재검사

- `docs/specs/mcp-data-contract.md`의 과거 STRONG/ANSWER 설명을 현재 코드와 맞게 정리했다.
- 기본 시간·진도 경계는 `remaining_time <= 15` AND `remaining_puzzle_ratio >= 0.50`으로 코드·문서·테스트를 정렬했다.
- `reason_codes`는 실행 코드, 평가셋, 과거 Draft의 명칭이 서로 달라 **임의 통합하지 않고 충돌 상태를 문서화**했다.
- 재요청 기준 60초/120초, Answer offer TTL 10분/과거 5분 문서, `/mcp` transport, 판정자, rubric, baseline, injection 평가, GM 우선순위 규칙은 팀 결정 또는 실제 실행 근거가 없으므로 생성하지 않았다.

## 수정 기획안 대조 — 2026-09-22 추가

기준 문서: `docs/01-operations-agent-problem-definition.md`

| 기획 항목 | 기존 폴더 상태 | 이번 처리 | 남은 점 |
|---|---|---|---|
| 운영 보조 Agent 정의 | README가 힌트 판단 Agent 중심 | README/Architecture/Status를 운영 보조 Agent 방향으로 정렬 | 관리자·운영 통계는 후속 |
| 게임마스터 요청 상태 | `PENDING` 시작 | `OPEN` 시작으로 코드·프론트·테스트·문서 정렬 | 실제 운영자 인증은 미구현 |
| 요청 상태 변경 MCP | 함수는 있으나 FastMCP 등록 누락 | `update_master_request` 등록 | 원격 `/mcp` transport는 미검증 |
| 고객의 진도 변경 금지 | `mark_puzzle_solved`가 FastMCP 및 public solve route에 노출 | FastMCP 등록과 public solve route에서 제거 | GM/internal event용 인증 계약 필요 |
| QR 후속 | QR payload/route가 P0에 노출 | active API와 frontend 계약에서 제거 | `qr_service.py` helper는 후속 참고용으로만 남김 |
| 일반 문의 분류 | `GENERAL_INQUIRY` 없음 | 임의 enum 추가 안 함 | 응답 상태/허용 데이터/평가 정답 합의 필요 |
| LLM 최종 문장 표현 | 현재 승인 힌트/코드 응답 직접 반환 | 임의 2차 LLM 호출 추가 안 함 | 출력 계약·실패 정책·평가 기준 필요 |
| 장비 이상 이력 | GM 요청 reason에 포함 | 현 상태 유지 | 별도 장애 이력 schema 확정 필요 |
| 여러 방 운영 요약/우선순위 | 정적 GM 화면 + 실제 요청 큐 | 자동 점수/우선순위 생성 안 함 | 전체 세션 조회 계약·팀 승인 규칙 필요 |
| 운영 요약·통계 | 없음 | 후속 범위 유지 | 원천 이벤트/집계 계약 필요 |
| RAG/LangGraph | 금지 유지 | 추가하지 않음 | 없음 |


### 수정 기획안 반영 후 재검증

- Backend compile: PASS
- Backend pytest: **57 passed**
- OpenAPI: QR route와 고객 solve route가 없음 확인
- LocalRuntime GM 요청 최초 상태: `OPEN` 확인
- FastMCP source 등록: `update_master_request` 포함, `mark_puzzle_solved` 제외 확인
- Escape Ops JS syntax: PASS
- Frontend Vitest: `node_modules` 부재로 미검증 (`vitest: not found`)
- FastMCP runtime import: 현재 검증 컨테이너의 `mcp` package 부재로 미검증
- Docker Compose: 현재 검증 컨테이너에 Docker CLI가 없어 미검증
