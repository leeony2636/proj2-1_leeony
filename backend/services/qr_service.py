from urllib.parse import urlencode


def build_qr_payload(session_id: str, team_id: str) -> str:
    """후속 QR 입장 검토용 payload helper. 현재 P0 HTTP API에는 연결하지 않는다."""
    query = urlencode({"team_id": team_id})
    return f"/join/{session_id}?{query}"
