# 향후 아키텍처 방향
P0: Vercel React + TypeScript + Vite → FastAPI → FastMCP → LocalRuntime
- LLM은 의도·감정·문장 생성을 담당한다.
- 세션 상태·진도·힌트 강도·직원 호출은 코드와 MCP가 결정한다.
- LocalRuntime은 P0 단일 인스턴스용이며, 다중 인스턴스 전 PostgreSQL로 교체한다.
- Azure OpenAI는 1순위 Provider 후보이고 현재 기본 실행은 baseline이다.
- RAG는 후속 검색 계층으로 분리한다.
운영 확장: Vercel → Azure Container Apps 등 컨테이너 런타임 → FastAPI/FastMCP → Azure OpenAI/PostgreSQL
Runtime Adapter: LocalRuntime(P0), Escapp Adapter(후속), ERCC Adapter(후속)
<!-- 통합 메모: temp-git의 Cloud Run 및 정적 HTML 전제를 Vercel + Vite 방향으로 수정했습니다. -->
