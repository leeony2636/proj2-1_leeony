"""FastAPI API entrypoint for the escape-room hint agent."""
from fastapi import FastAPI

from backend.routers.agent import router as agent_router
from backend.routers.answers import router as answers_router
from backend.routers.master import router as master_router
from backend.routers.sessions import router as sessions_router
from backend.routers.stt import router as stt_router

# Vercel이 React 정적 프론트엔드를 담당하므로 FastAPI는 API/MCP와 health만 제공합니다.
# temp-git의 정적 HTML 응답은 현재 단일 Vite 앱 구조와 충돌해 제외했습니다.
app = FastAPI(title="방탈출 진행자 힌트 판단 Agent", version="0.3.0")
app.include_router(sessions_router)
app.include_router(agent_router)
app.include_router(master_router)
app.include_router(answers_router)
app.include_router(stt_router)

@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
