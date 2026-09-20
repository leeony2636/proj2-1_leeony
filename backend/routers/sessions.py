from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
import qrcode
import qrcode.image.svg
from backend.schemas import CreateSessionRequest,SolvePuzzleRequest
from backend.services.mcp_client import MCPClient
from backend.services.qr_service import build_qr_payload
router=APIRouter(prefix="/api",tags=["sessions"]); mcp=MCPClient()
@router.get("/themes")
def themes(): return {"themes":mcp.list_themes()}
@router.post("/sessions")
def create_session(payload:CreateSessionRequest)->dict:
    try: s=mcp.create_session(payload.theme_id,payload.team_id)
    except (KeyError,ValueError) as exc: raise HTTPException(400,str(exc)) from exc
    return {"session":s,"qr_payload":build_qr_payload(s["session_id"],s["team_id"])}
@router.get("/sessions/{session_id}")
def read_session(session_id:str)->dict:
    try:return mcp.get_session(session_id)
    except KeyError as exc: raise HTTPException(404,str(exc)) from exc
@router.post("/sessions/{session_id}/solve")
def solve(session_id:str,payload:SolvePuzzleRequest)->dict:
    try:return mcp.solve(session_id,payload.puzzle_id)
    except KeyError as exc: raise HTTPException(404,str(exc)) from exc
@router.get("/sessions/{session_id}/qr.svg")
def qr_svg(session_id:str,team_id:str):
    url=build_qr_payload(session_id,team_id)
    img=qrcode.make(url,image_factory=qrcode.image.svg.SvgPathImage)
    from io import BytesIO
    buf=BytesIO(); img.save(buf)
    return Response(content=buf.getvalue(),media_type="image/svg+xml")
