from urllib.parse import urlencode


def build_qr_payload(session_id: str, team_id: str) -> str:
    """QR 이미지에 넣을 고객 입장 URL payload."""
    query = urlencode({"team_id": team_id})
    return f"/join/{session_id}?{query}"
