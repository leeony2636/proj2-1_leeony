from fastapi import APIRouter
from backend.services.mcp_client import MCPClient
router=APIRouter(prefix="/api/master",tags=["master"]); mcp=MCPClient()
@router.get("/requests")
def master_requests(): return {"requests":mcp.master_requests()}
