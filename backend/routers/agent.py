from fastapi import APIRouter, HTTPException

from backend.schemas import AgentRequest, AgentResponse
from backend.services.agent_orchestrator import handle_agent_request

router = APIRouter(prefix="/api", tags=["agent"])


@router.post("/agent", response_model=AgentResponse)
def agent(payload: AgentRequest) -> AgentResponse:
    # 수정 사유: STRONG은 코드가 정책을 확인한 뒤 자동 제공한다.
    # ANSWER 동의 API는 정답 콘텐츠와 동의 계약 확정 후 별도로 추가한다.
    try:
        return handle_agent_request(payload)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
