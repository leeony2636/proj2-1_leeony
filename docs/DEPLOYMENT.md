# Deployment Options

## P0 기준

P0는 `React + TypeScript + Vite` frontend, FastAPI backend, FastMCP 도구 계층, LocalRuntime을 Docker Compose로 로컬 검증하는 단계입니다. frontend는 Vercel 정적 배포 대상으로 둡니다.

## P1 후보

| 후보 | 구성 | 장점 | 결정 시점 |
|---|---|---|---|
| Google Cloud | Vercel + Dockerized FastAPI/MCP + Cloud Run + Cloud SQL | Docker와 Cloud Run으로 로컬·배포 차이를 줄이기 쉬움 | P0와 Docker Compose 검증 후 |
| Azure | Vercel + Dockerized FastAPI/MCP + Azure Container Apps + Azure PostgreSQL + Azure OpenAI | 현재 Azure OpenAI 1순위 방향과 연결 | Azure 계정·크레딧·운영 담당 확정 후 |

## 공통 전제

- Dockerfile은 FastAPI/MCP backend의 실행 경계를 정의한다.
- frontend와 backend의 환경변수는 분리한다.
- LocalRuntime을 다중 인스턴스에 그대로 사용하지 않는다.
- 배포 전 PostgreSQL Repository와 관측 trace를 먼저 검증한다.
- PostgreSQL 전환 시 `RUNTIME_REPOSITORY=postgres`를 설정하고, 실제 연결 문자열·migration·재시작 보존을 별도 smoke test로 통과시킨다.
- FastMCP network transport를 사용할 때도 공통 schema와 권한 검증은 유지한다.

## 선택 기준

팀 계정·크레딧, PostgreSQL 운영 편의성, LLM Provider 선택, 로그·비용 관리 능력, 담당자의 배포 경험을 비교해 선택한다. RAG와 LangGraph는 사용하지 않으며, QR·ERCC/Escapp Adapter와 배포 플랫폼 확장은 P0 계약과 테스트가 안정화된 뒤 별도로 검토한다.
