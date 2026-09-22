# Route verification

## FastAPI HTTP routes

- `GET /health`
- `GET /api/themes`
- `POST /api/sessions`
- `GET /api/sessions/{session_id}`
- `POST /api/agent`
- `POST /api/agent/voice`
- `GET /api/master/requests`
- `POST /api/master/requests/{request_id}/acknowledge`
- `POST /api/master/requests/{request_id}/resolve`
- `POST /api/master/requests/{request_id}/cancel`
- `POST /api/answers/confirm`

Frontend routes are `/customer` and `/game-master`.

### 의도적으로 공개하지 않는 P0 route

- QR 입장/QR SVG: 수정 기획안에서 후속 확장
- 고객용 퍼즐 solve endpoint: 고객 Agent가 진도를 변경하면 안 되므로 비공개

진도 변경 Runtime 함수는 내부에 남아 있으나 게임마스터/내부 이벤트용 인증·계약이 확정될 때까지 HTTP/MCP 고객 경로에 공개하지 않는다.

## MCP tool boundary

`mcp_server/server.py` registers the domain tools with `FastMCP`. `mark_puzzle_solved` is intentionally not registered, while `update_master_request` is registered for the GM request lifecycle.

The current FastAPI process does **not** expose a verified Streamable HTTP `/mcp` endpoint, and `docker-compose.yml` does not run a separate MCP transport service.

Therefore the delivery-guide requirement `POST /api/agent` vs `/mcp` separation is only partially implemented: the tool contract exists, but the deployed `/mcp` transport is not yet verified. Do not describe `/mcp` as deployed until that connection is tested.

```bash
docker compose exec api python -c "from backend.main import app; print([r.path for r in app.routes])"
```
