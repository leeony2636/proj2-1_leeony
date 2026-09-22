from datetime import datetime, timezone

from backend.repositories.postgres import PostgresRepository
from backend.repositories.memory import MemoryRepository
from mcp_server.adapters.local_runtime import _build_default_repository
from backend.schemas import HintEvent, HintStrength, SessionState


def _session() -> SessionState:
    return SessionState(
        session_id="repo-session-1",
        team_id="repo-team-1",
        theme_id="last_train",
        started_at=datetime.now(timezone.utc),
        duration_minutes=60,
        total_puzzles=12,
        current_puzzle_id="train-p01",
    )


def test_memory_repository_stores_session_and_hint_history():
    repository = MemoryRepository()
    session = _session()
    event = HintEvent(
        session_id=session.session_id,
        team_id=session.team_id,
        puzzle_id=session.current_puzzle_id,
        strength=HintStrength.WEAK,
        delivered_at=datetime.now(timezone.utc),
        reason_codes=["DEFAULT_WEAK"],
        idempotency_key="repo-hint-1",
    )

    repository.save_session(session)
    repository.append_hint_event(event)

    assert repository.get_session(session.session_id) == session
    assert repository.list_hint_events(session.session_id, session.current_puzzle_id) == [event]


def test_memory_repository_keeps_idempotency_payload_and_result():
    repository = MemoryRepository()

    repository.save_idempotency(
        "repo-key-1",
        {"session_id": "s1"},
        {"ok": True, "deduplicated": False},
    )

    stored = repository.get_idempotency("repo-key-1")
    assert stored == ({"session_id": "s1"}, {"ok": True, "deduplicated": False})


def test_memory_repository_stores_and_updates_master_request():
    repository = MemoryRepository()
    request = {
        "request_id": "master-repo-1",
        "session_id": "repo-session-1",
        "team_id": "repo-team-1",
        "reason": "CUSTOMER_REQUEST",
        "status": "OPEN",
    }

    repository.save_master_request(request)
    request["status"] = "ACKNOWLEDGED"
    repository.update_master_request(request)

    assert repository.get_master_request("master-repo-1")["status"] == "ACKNOWLEDGED"
    assert repository.list_master_requests()[0]["request_id"] == "master-repo-1"


def test_runtime_repository_factory_keeps_memory_as_default(monkeypatch):
    monkeypatch.delenv("RUNTIME_REPOSITORY", raising=False)

    assert isinstance(_build_default_repository(), MemoryRepository)


def test_runtime_repository_factory_selects_postgres(monkeypatch):
    monkeypatch.setenv("RUNTIME_REPOSITORY", "postgres")
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://app:app@db:5432/app")

    repository = _build_default_repository()

    assert isinstance(repository, PostgresRepository)
    assert repository.dsn == "postgresql://app:app@db:5432/app"
