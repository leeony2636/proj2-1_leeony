# 향후 아키텍처 방향
P0: Vercel React + TypeScript + Vite → FastAPI → FastMCP → LocalRuntime
- LLM은 의도·감정·문장 생성을 담당한다.
- 세션 상태·진도·힌트 강도·직원 호출은 코드와 MCP가 결정한다.
- LocalRuntime은 P0 단일 인스턴스용이며, 다중 인스턴스 전 PostgreSQL로 교체한다.
- 현재 A안으로 `RuntimeRepository`와 `MemoryRepository`를 분리했으며, B안에서 PostgreSQL Repository가 같은 계약을 구현한다.
- B안 1차로 `PostgresRepository`와 `backend/db/schema.sql`을 추가했으며, `RUNTIME_REPOSITORY=postgres`로 선택한다. 실제 서버 연결·migration·다중 인스턴스 검증은 후속 단계다.
- Azure OpenAI는 1순위 Provider 후보이고 현재 기본 실행은 baseline이다.
- RAG와 LangGraph는 사용하지 않는다. 후속 확장도 승인된 정적 콘텐츠와 코드/MCP 계약을 유지한다.
운영 확장 후보:

- A안: Vercel → Google Cloud Run(Docker) → FastAPI/FastMCP → Cloud SQL/PostgreSQL
- B안: Vercel → Azure Container Apps(Docker) → FastAPI/FastMCP → Azure PostgreSQL/Azure OpenAI

P0 안정화 후 팀 계정, 비용, 로그 운영 역량, LLM Provider 선택을 기준으로 A안과 B안 중 하나를 결정한다. 컨테이너 경계와 공통 schema는 두 후보에서 동일하게 유지한다.
Runtime Adapter: LocalRuntime(P0), Escapp Adapter(후속), ERCC Adapter(후속)
