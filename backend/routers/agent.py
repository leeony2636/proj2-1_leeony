from fastapi import APIRouter, HTTPException

from backend.schemas import AgentRequest, AgentResponse
from backend.services.agent_orchestrator import handle_agent_request

router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/agent", response_model=AgentResponse)
def agent(payload: AgentRequest) -> AgentResponse:
    try:
        return handle_agent_request(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
