from __future__ import annotations

from threading import Lock

from backend.repositories.protocol import RuntimeRepository
from backend.schemas import ConversationTurn, HintEvent, SessionState


class MemoryRepository(RuntimeRepository):
    """P0 단일 프로세스용 Repository.

    수정 사유: 기존 LocalRuntime의 전역 컬렉션을 저장소 객체 안으로 이동해
    PostgreSQL Repository가 같은 계약을 구현할 수 있게 한다.
    """

    def __init__(self) -> None:
        self._sessions: dict[str, SessionState] = {}
        self._hint_events: list[HintEvent] = []
        self._master_requests: list[dict] = []
        self._idempotency: dict[str, tuple[dict, dict]] = {}
        self._conversation_turns: dict[str, list[ConversationTurn]] = {}
        self._lock = Lock()

    def save_session(self, session: SessionState) -> None:
        with self._lock:
            self._sessions[session.session_id] = session

    def get_session(self, session_id: str) -> SessionState | None:
        with self._lock:
            return self._sessions.get(session_id)

    def append_hint_event(self, event: HintEvent) -> None:
        with self._lock:
            self._hint_events.append(event)

    def list_hint_events(self, session_id: str, puzzle_id: str) -> list[HintEvent]:
        with self._lock:
            return [
                event
                for event in self._hint_events
                if event.session_id == session_id and event.puzzle_id == puzzle_id
            ]

    def get_idempotency(self, key: str) -> tuple[dict, dict] | None:
        with self._lock:
            stored = self._idempotency.get(key)
            if stored is None:
                return None
            return dict(stored[0]), dict(stored[1])

    def save_idempotency(self, key: str, payload: dict, result: dict) -> None:
        with self._lock:
            self._idempotency[key] = (dict(payload), dict(result))

    def save_master_request(self, request: dict) -> None:
        with self._lock:
            self._master_requests.append(dict(request))

    def get_master_request(self, request_id: str) -> dict | None:
        with self._lock:
            request = next(
                (item for item in self._master_requests if item["request_id"] == request_id),
                None,
            )
            return dict(request) if request else None

    def update_master_request(self, request: dict) -> None:
        with self._lock:
            for index, item in enumerate(self._master_requests):
                if item["request_id"] == request["request_id"]:
                    self._master_requests[index] = dict(request)
                    return
            raise KeyError(f"MASTER_REQUEST_NOT_FOUND:{request['request_id']}")

    def list_master_requests(self) -> list[dict]:
        with self._lock:
            return [dict(item) for item in self._master_requests]

    def append_conversation_turn(self, session_id: str, turn: ConversationTurn) -> None:
        with self._lock:
            self._conversation_turns.setdefault(session_id, []).append(turn)

    def list_conversation_turns(self, session_id: str, limit: int = 6) -> list[ConversationTurn]:
        with self._lock:
            turns = self._conversation_turns.get(session_id, [])
            return list(turns[-max(limit, 0):])
