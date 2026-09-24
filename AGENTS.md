# AGENTS.md

AI 코딩 에이전트(Claude Code, Codex, Cursor 등)가 이 저장소에서 작업할 때 따르는 공통 지침입니다. 어떤 도구를 쓰든 이 문서를 기준으로 합니다.

## 프로젝트 개요

방탈출 카페 고객의 힌트·장비 이상·직원 호출·운영 상태 문의를 연결하는 운영 보조 Agent를 개발합니다. 기존 힌트 제공은 고객 지원 모듈로 유지합니다.

## 기술 스택과 구현 단계

### P0 현재 기준

1. 개발 언어: Python / TypeScript / HTML / CSS
2. 백엔드: FastAPI / Pydantic / Uvicorn
3. MCP 도구 구조: FastMCP
4. 데이터 저장: 메모리 기반 `LocalRuntime`
5. 프론트엔드: React / TypeScript / Vite
6. 관측·로그: Langfuse safe allowlist와 평가 score 기록 코드 구현, 실제 계정 연결은 팀 환경에서 검증
7. 실행: Docker / Docker Compose
8. 프론트엔드 배포 후보: Vercel

테스트 기본 transport는 같은 프로세스의 contract dispatcher이며, Compose는 FastMCP Streamable HTTP 경로를 설정합니다. `PostgreSQL`은 선택형 repository입니다. 실제 외부 배포와 Langfuse 계정 연결은 팀 환경에서 별도 검증합니다.

### P1 후속 후보

- Google Cloud: Vercel + Dockerized FastAPI/MCP + Cloud Run + Cloud SQL
- Azure: Vercel + Dockerized FastAPI/MCP + Azure Container Apps + Azure PostgreSQL + Azure OpenAI
- FastMCP 네트워크 transport
- PostgreSQL Repository와 다중 인스턴스 운영
- Vertex AI 또는 Azure OpenAI Provider 연결
- 실제 Langfuse trace·평가 연동

배포 후보의 비교 기준은 `docs/DEPLOYMENT.md`를 따릅니다. 구현되지 않은 외부 연결을 완료된 기능처럼 보고하지 않습니다.

## Agent 책임 경계

### LLM이 담당하는 일

- 고객 자연어의 복합 의도와 지원 필요도 판단
- 명시적 감정 신호 구조화
- 문제 식별과 추가 정보 필요 여부 판단
- 필요한 읽기 전용 MCP 도구 선택과 결과에 따른 최대 1회 후속 판단
- 승인된 결과의 자연어 표현

### LLM이 담당하지 않는 일

- 승인되지 않은 힌트 강도/본문의 임의 확정
- 남은 시간·진도율 계산
- 세션·팀 권한 검증
- `AnswerVault` 직접 조회
- 승인되지 않은 힌트 생성
- 장비 이상을 임의로 해결했다고 판단
- 직원 호출 여부의 최종 결정

LLM은 `STANDARD/STRONG/ANSWER` 지원 필요도를 맥락상 판단한다. 코드는 이를 승인된 WEAK/STRONG 콘텐츠 경계에 매핑하고 세션 상태, 진도, 스포일러 차단, 직원 호출의 실행 권한을 강제한다. `15분/50%`와 재요청 자동 STRONG 승격은 팀 미확정이다. 실제 LLM 미설정 시 baseline으로 조용히 대체하지 않는다.

## MCP 작업 경로

- 운영 도구: `mcp_server/tools/`
- 서버 등록: `mcp_server/server.py`
- Runtime Adapter: `mcp_server/adapters/`
새 운영 도구는 `mcp_server/tools/`에 작성합니다. 서버 등록과 공통 검증은 `mcp_server/server.py` 및 `mcp_server/contract_dispatch.py`에서 확인합니다.

MCP 도구명과 입력·출력 schema의 현재 정본은 `mcp_server/server.py`, `mcp_server/schemas.py`, `mcp_server/contract_dispatch.py`와 관련 테스트입니다. Draft 계약 문서를 현재 구현으로 오인하지 않습니다. 이름을 변경할 때 등록 코드, FastAPI adapter, 테스트를 함께 수정합니다.

## 세션·권한·상태 검증 규칙

모든 MCP 읽기·쓰기 도구는 다음 순서를 지킵니다.

1. `session_id` 존재 확인
2. `session_id`와 `team_id` 일치 확인
3. 세션 종료 여부 확인
4. 현재 퍼즐과 요청 퍼즐의 순서 확인
5. 쓰기 작업이면 `idempotency_key` 확인
6. 검증 통과 후 상태 변경

검증 실패 시 MCP write를 실행하지 않습니다. 장비 이상 신고와 게임마스터 직접 요청도 동일한 세션·팀 검증을 거칩니다.

WEAK와 STRONG은 승인된 콘텐츠만 사용하고 코드 정책을 통과하면 자동 제공한다. `offer_id` 동의는 STRONG에 적용하지 않으며, ANSWER 요청에만 일회성 동의 토큰으로 사용한다. `idempotency_key`와 영속 저장소는 현재 후속 작업이므로 실제 구현 여부를 확인해 완료를 보고한다.

## Spec 먼저, 구현은 그다음

기능을 에이전트에게 시키기 전에 `docs/specs/{기능명}.md`에 Spec을 먼저 작성하세요. 형식은 `docs/specs/_example.md`를 참고합니다. 다섯 섹션(Why · Goal · What · How · AC)이 모두 있어야 합니다.

- **Why**: 페르소나·상황·문제·측정 지표
- **Goal**: 숫자로 된 성공 기준 + Out of Scope
- **What**: Happy Path + Edge Case
- **How**: API·데이터·제약
- **AC**: Given-When-Then 형식

계약 문서가 Draft이면 구현 완료로 간주하지 말고, 실제 코드명·입출력 schema·테스트 상태를 함께 확인합니다.

## 테스트와 완료 기준

관련 변경 후 실제 실행한 검증 명령과 결과만 완료 보고에 기록합니다. 상세 명령은 `docs/TESTING.md`를 참고합니다.

```powershell
py -3 -m compileall -q backend mcp_server
py -3 -m pytest backend/tests -q

Set-Location frontend
npm test -- --run
npm run build
```

Backend 의존성이 없어서 pytest를 실행하지 못한 경우 문법 검사 성공을 테스트 통과로 표현하지 않습니다. 테스트가 AC를 통과하지 않으면 “완료”라고 보고하지 않습니다.

## Git 작업 규칙

- `main`에 직접 push하지 않습니다.
- 작업 브랜치는 작성자 성명 이니셜 + 생성 순번을 사용합니다. 예: `STH004`
- 사용자가 명시하지 않은 commit, push, merge, PR 생성은 수행하지 않습니다.
- 작업 전 현재 branch와 working tree 상태를 확인합니다.
- 기존 사용자 변경 사항을 삭제하거나 `git reset --hard`, `git checkout --`으로 덮어쓰지 않습니다.
- 완료 보고에는 branch, 변경 파일, 검증 결과, commit/push 여부를 명시합니다.
- 코드 생성 및 수정시 주석으로 수정내용 및 기능 명세 작성합니다.

## Out of Scope 원칙

에이전트는 Spec에 없는 기능을 임의로 추가하지 않습니다. “이왕이면”으로 범위를 넓히지 않습니다.

RAG와 LangGraph는 이 프로젝트에서 사용하지 않습니다. QR 입장, ERCC/Escapp Adapter, 다중 매장 권한, 실제 장비 제어, 배포 플랫폼 전환도 P0 범위에 포함하지 않습니다.

## 문서 갱신 규칙

구현 상태가 바뀌면 다음 문서도 함께 확인합니다.

- `README.md`: 팀 실행·협업 안내
- `docs/RUN_NOW.md`: 로컬 실행 절차
- `docs/STATUS.md`: 구현됨·검증됨·미검증 구분
- `mcp_server/server.py`, `mcp_server/schemas.py`: MCP 도구 등록과 계약
- `docs/TESTING.md`: 검증 명령과 통합 테스트 순서
- `docs/DEPLOYMENT.md`: Google Cloud Run과 Azure Container Apps 선택지
- `EVAL_REPORT.md`: 평가 실행 metadata와 개선 전후 결과

## 주석 작성 규칙

- 정책·보안·권한·상태 전이·예외 처리 로직에는 반드시 한국어 주석으로 작성 사유와 의도를 설명한다.
- 단순한 변수 선언이나 명확한 API 연결 코드에는 불필요한 주석을 남기지 않는다.
- 기존 코드를 수정할 때 동작 변경의 이유와 기존 방식과 달라진 점을 주석으로 남긴다.
- 주석은 코드의 동작을 반복하지 말고, 왜 그렇게 구현했는지를 설명한다.
