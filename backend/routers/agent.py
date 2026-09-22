from fastapi import APIRouter, HTTPException

from backend.schemas import AgentRequest, AgentResponse
from backend.services.agent_orchestrator import handle_agent_request

router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/agent", response_model=AgentResponse)
def agent(payload: AgentRequest) -> AgentResponse:
    # support_need의 의미 판단은 LLM이 하고, 코드는 승인된 WEAK/STRONG 콘텐츠 경계만 강제한다.
    # ANSWER는 별도 AnswerVault/동의 경계를 유지한다.
    try:
        return handle_agent_request(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
