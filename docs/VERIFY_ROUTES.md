# Route verification
FastAPI API: `/health`, `/api/themes`, `/api/sessions`, `/api/sessions/{session_id}`, `/api/agent`, `/api/master/requests`, `/api/answers/reveal`
Frontend: Vite/Vercel routes `/customer` and `/game-master`

    docker compose exec api python -c "from backend.main import app; print([r.path for r in app.routes])"
<!-- 통합 메모: 정적 HTML 라우트는 FastAPI에서 제거하고 Vite/Vercel로 분리했습니다. -->
