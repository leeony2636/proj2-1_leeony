from fastapi import APIRouter, HTTPException
from backend.schemas import MasterRequestActionRequest
from backend.services.mcp_client import MCPClient
router=APIRouter(prefix="/api/master",tags=["master"]); mcp=MCPClient()
@router.get("/requests")
def master_requests(): return {"requests":mcp.master_requests()}


def _update(request_id: str, status: str, payload: MasterRequestActionRequest) -> dict:
    try:
        return mcp.update_master_request(
            request_id,
            status,
            payload.operator_id,
            payload.note,
            payload.idempotency_key,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/requests/{request_id}/acknowledge")
def acknowledge(request_id: str, payload: MasterRequestActionRequest) -> dict:
    return _update(request_id, "ACKNOWLEDGED", payload)


@router.post("/requests/{request_id}/resolve")
def resolve(request_id: str, payload: MasterRequestActionRequest) -> dict:
    return _update(request_id, "RESOLVED", payload)


@router.post("/requests/{request_id}/cancel")
def cancel(request_id: str, payload: MasterRequestActionRequest) -> dict:
    return _update(request_id, "CANCELED", payload)
