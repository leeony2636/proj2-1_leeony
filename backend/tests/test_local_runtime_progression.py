from backend.repositories.memory import MemoryRepository
from mcp_server.adapters.local_runtime import LocalRuntime


def test_mark_puzzle_solved_moves_to_next_unsolved_puzzle():
    # 수정 사유: 문제 완료 후 Repository에 저장된 다음 문제까지 검증해
    # 지역 변수명 오류가 다시 병합되는 회귀를 막는다.
    repository = MemoryRepository()
    runtime = LocalRuntime(repository)
    session = runtime.create_session("professors_lab", "team-progress-next")
    solved_puzzle_id = session.current_puzzle_id

    updated = runtime.mark_puzzle_solved(session.session_id, solved_puzzle_id)
    stored = repository.get_session(session.session_id)

    assert solved_puzzle_id in updated.solved_puzzle_ids
    assert updated.solved_puzzles == 1
    assert updated.current_puzzle_id != solved_puzzle_id
    assert stored == updated


def test_mark_last_puzzle_solved_closes_session():
    repository = MemoryRepository()
    runtime = LocalRuntime(repository)
    session = runtime.create_session("professors_lab", "team-progress-close")
    puzzle_ids = [
        puzzle["puzzle_id"]
        for puzzle in runtime._theme(session.theme_id)["puzzles"]
    ]

    for puzzle_id in puzzle_ids:
        updated = runtime.mark_puzzle_solved(session.session_id, puzzle_id)

    stored = repository.get_session(session.session_id)

    assert updated.is_closed is True
    assert updated.current_puzzle_id is None
    assert updated.solved_puzzles == updated.total_puzzles
    assert stored == updated
