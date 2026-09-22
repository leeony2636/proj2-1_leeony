from mcp_server.adapters.local_runtime import LocalRuntime

runtime = LocalRuntime()


def list_themes() -> list[dict]:
    return runtime.list_themes()


def create_game_session(theme_id: str, team_id: str) -> dict:
    return runtime.create_session(theme_id, team_id).model_dump(mode="json")


def get_game_session(session_id: str) -> dict:
    return runtime.get_game_session(session_id).model_dump(mode="json")


def mark_puzzle_solved(session_id: str, puzzle_id: str) -> dict:
    return runtime.mark_puzzle_solved(session_id, puzzle_id).model_dump(mode="json")
