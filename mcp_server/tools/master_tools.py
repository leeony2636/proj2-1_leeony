from mcp_server.adapters.local_runtime import LocalRuntime

runtime = LocalRuntime()


def request_game_master(
    session_id: str,
    team_id: str,
    reason: str,
    idempotency_key: str | None = None,
) -> dict:
    return runtime.request_game_master(session_id, team_id, reason, idempotency_key)


def report_equipment_issue(
    session_id: str,
    team_id: str,
    detail: str,
    idempotency_key: str | None = None,
) -> dict:
    return runtime.report_equipment_issue(session_id, team_id, detail, idempotency_key)


def get_master_requests() -> list[dict]:
    return runtime.get_master_requests()


def update_master_request(
    request_id: str,
    status: str,
    operator_id: str,
    note: str = "",
    idempotency_key: str | None = None,
) -> dict:
    return runtime.update_master_request(
        request_id, status, operator_id, note, idempotency_key
    )
