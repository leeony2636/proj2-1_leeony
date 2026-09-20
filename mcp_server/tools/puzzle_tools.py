from mcp_server.adapters.local_runtime import LocalRuntime

runtime = LocalRuntime()


def get_puzzle_context(theme_id: str, puzzle_id: str) -> dict:
    return runtime.get_puzzle_context(theme_id, puzzle_id)
