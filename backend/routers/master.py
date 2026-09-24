from fastapi import APIRouter, Depends, HTTPException

from backend.schemas import MasterRequestActionRequest
from backend.services.master_auth import MasterPrincipal, require_game_master_access
from backend.services.mcp_client import MCPClient

router = APIRouter(prefix="/api/master", tags=["master"])
mcp = MCPClient()


@router.get("/requests")
def master_requests(
    _: MasterPrincipal = Depends(require_game_master_access),
) -> dict:
    return {"requests": mcp.master_requests()}


def _update(
    request_id: str,
    status: str,
    payload: MasterRequestActionRequest,
    principal: MasterPrincipal,
) -> dict:
    try:
        # operator_id는 하위 호환 body 필드일 뿐 인증 근거로 사용하지 않는다.
        # 실제 변경 주체는 검증된 principal.subject이다.
        return mcp.update_master_request(
            request_id,
            status,
            principal.subject,
            payload.note,
            payload.idempotency_key,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/requests/{request_id}/acknowledge")
def acknowledge(
    request_id: str,
    payload: MasterRequestActionRequest,
    principal: MasterPrincipal = Depends(require_game_master_access),
) -> dict:
    return _update(request_id, "ACKNOWLEDGED", payload, principal)


@router.post("/requests/{request_id}/resolve")
def resolve(
    request_id: str,
    payload: MasterRequestActionRequest,
    principal: MasterPrincipal = Depends(require_game_master_access),
) -> dict:
    return _update(request_id, "RESOLVED", payload, principal)


@router.post("/requests/{request_id}/cancel")
def cancel(
    request_id: str,
    payload: MasterRequestActionRequest,
    principal: MasterPrincipal = Depends(require_game_master_access),
) -> dict:
    return _update(request_id, "CANCELED", payload, principal)
