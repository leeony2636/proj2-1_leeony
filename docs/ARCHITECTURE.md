# Architecture

## P0 구조

```text
Customer / GameMaster UI
          |
          v
       FastAPI
          |
          +-- services/llm.py
          |      └─ 자연어 의도/감정 구조화
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
      LocalRuntime
```

현재 `MCPClient`는 로컬 함수 호출로 연결된 P0 골격입니다.
실제 FastMCP transport를 붙일 때 `backend/services/mcp_client.py` 내부만 교체하는 방향입니다.

## 외부 Runtime 확장

```text
MCP Tool
  └─ Runtime Adapter
       ├─ LocalRuntime    (P0)
       ├─ EscappAdapter   (후속 검토)
       └─ ERCCAdapter     (후속 검토)
```

외부 제품 API를 Agent가 직접 호출하지 않게 분리합니다.

프론트엔드는 하나의 React + TypeScript + Vite 앱에서 `/customer`와 `/game-master`를 제공하고 Vercel에 정적 배포합니다.
<!-- 통합 메모: temp-git의 정적 HTML 화면 대신 현재 확정된 단일 Vite 앱을 기준으로 설명합니다. -->

## DB

강사 scaffold에는 PostgreSQL 서비스가 기본 포함되어 있습니다.
현재 LocalRuntime은 메모리 저장소이므로 실제 Backend/MCP 분리 배포 전에는
공유 DB 모델로 교체해야 합니다.
