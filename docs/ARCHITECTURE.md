# Architecture

> 2026-09-23 운영 보조 통합 메모: 현재 Agent 실행 경로는 [PROJECT_PLAN.md](./PROJECT_PLAN.md)의 세션 preflight → Domain Skill/최근 대화 → LLM INITIAL → 선택 조회 및 최대 1회 FOLLOWUP → 코드/MCP 실행이다. 아래 기존 도식 중 고정 조회 순서·코드의 의미상 힌트 강도 판정 설명은 과거 힌트 전용 설계 기록으로 읽는다. 실제 호출 관계는 `backend/services/agent_orchestrator.py`와 테스트가 우선한다.

## P0 구조

```text
Customer / GameMaster UI
          |
          +-- text input ------------------+
          +-- voice submit → STT Adapter --+
                                           v
       FastAPI
          |
          +-- services/llm.py
          |      └─ STT 결과 텍스트의 의도/감정 구조화
          |
          +-- agent_orchestrator.py
          |
          v
      MCP Client
          |
          v
     MCP Tool Layer
          |
          v
   RuntimeRepository
        ├─ MemoryRepository (P0 기본)
        └─ PostgresRepository (선택형 B안 1차)
```

## STT 입력 경계

- STT는 음성 파일 또는 브라우저 녹음 결과를 텍스트로 변환하는 입력 Adapter다.
- STT는 의도, 감정, 힌트 강도, 정답을 판단하지 않는다. 변환된 텍스트만 `AgentRequest.message`로 전달한다.
- MVP는 고객이 음성 요청 버튼을 눌러 제출하는 방식이며 상시 마이크 청취·선제 개입은 범위에서 제외한다.
- 빈 전사, 낮은 신뢰도, 변환 실패는 LLM/MCP 판정 전에 재입력 요청으로 종료한다.
- Provider와 모델은 `services/stt.py` 또는 동등한 Adapter 경계 뒤에 둔다. 특정 STT 모델을 현재 확정하지 않는다.

`backend/services/mcp_transport.py`는 기본 InProcess transport와 선택 Streamable HTTP transport를 제공합니다. Docker Compose는 FastAPI와 FastMCP를 별도 서비스로 띄워 HTTP 경로를 사용하고, 단위 테스트는 동일 contract dispatcher를 거치는 in-process 경로를 씁니다. 실제 배포 환경의 네트워크·권한 설정은 별도 검증 대상입니다.

## 외부 Runtime 확장

```text
MCP Tool
  └─ Runtime Adapter
       ├─ LocalRuntime    (P0)
       └─ PostgreSQL Repository (선택형 저장소)
```

외부 제품 Adapter는 확정된 연동 계약과 팀 우선순위가 생길 때 추가합니다. 현재 저장소에는 미연결 Adapter placeholder를 두지 않습니다.

프론트엔드는 하나의 React + TypeScript + Vite 앱에서 `/customer`와 `/game-master`를 제공하고 Vercel에 정적 배포합니다.
<!-- 통합 메모: temp-git의 정적 HTML 화면 대신 현재 확정된 단일 Vite 앱을 기준으로 설명합니다. -->

## DB

강사 scaffold에는 PostgreSQL 서비스가 기본 포함되어 있습니다.
현재 P0 기본값은 `MemoryRepository`이며, `RUNTIME_REPOSITORY=postgres`로
`PostgresRepository`를 선택할 수 있습니다. 실제 DB 연결·migration·복구·다중
인스턴스 운영은 아직 외부 검증이 필요한 후속 단계입니다.
