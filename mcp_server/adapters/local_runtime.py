from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import json
import os
import uuid

from backend.repositories.memory import MemoryRepository
from backend.repositories.protocol import RuntimeRepository
from backend.schemas import ConversationTurn, HintEvent, SessionState


ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "backend" / "data"


def _build_default_repository() -> RuntimeRepository:
    """환경변수로 저장소를 선택하되 기본값은 P0 memory로 유지한다."""
    repository_kind = os.getenv("RUNTIME_REPOSITORY", "memory").strip().lower()
    if repository_kind == "postgres":
        # 수정 사유: 운영/통합환경에서만 PostgreSQL을 선택하고, 기본 개발 환경은
        # 외부 DB 없이 기존 LocalRuntime을 실행할 수 있어야 한다.
        from backend.repositories.postgres import PostgresRepository

        return PostgresRepository(os.getenv("DATABASE_URL", "").strip())
    if repository_kind != "memory":
        raise ValueError(f"RUNTIME_REPOSITORY_UNSUPPORTED:{repository_kind}")
    return MemoryRepository()


_DEFAULT_REPOSITORY = _build_default_repository()


class LocalRuntime:
    def __init__(self, repository: RuntimeRepository | None = None) -> None:
        # 수정 사유: 기본값은 기존 P0 메모리 동작을 유지하고, 테스트·PostgreSQL 전환 시
        # Repository를 주입할 수 있도록 한다.
        self.repository = repository or _DEFAULT_REPOSITORY

    def _theme(self, theme_id: str) -> dict:
        path = DATA_DIR / "themes" / f"{theme_id}.json"
        if not path.exists():
            raise KeyError(f"THEME_NOT_FOUND:{theme_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def _hints(self, theme_id: str) -> dict:
        path = DATA_DIR / "hints" / f"{theme_id}.json"
        if not path.exists():
            raise KeyError(f"HINT_DATA_NOT_FOUND:{theme_id}")
        return json.loads(path.read_text(encoding="utf-8"))

    def list_themes(self) -> list[dict]:
        out = []
        for path in sorted((DATA_DIR / "themes").glob("*.json")):
            theme = json.loads(path.read_text(encoding="utf-8"))
            out.append({
                "theme_id": theme["theme_id"],
                "title": theme["title"],
                "duration_minutes": theme["duration_minutes"],
                "total_puzzles": len(theme["puzzles"]),
                "difficulty": theme.get("difficulty"),
            })
        return out

    def create_session(self, theme_id: str, team_id: str) -> SessionState:
        theme = self._theme(theme_id)
        puzzles = theme.get("puzzles", [])
        if not puzzles:
            raise ValueError(f"THEME_HAS_NO_PUZZLES:{theme_id}")
        session = SessionState(
            session_id=str(uuid.uuid4()),
            team_id=team_id,
            theme_id=theme_id,
            started_at=datetime.now(timezone.utc),
            duration_minutes=int(theme["duration_minutes"]),
            total_puzzles=len(puzzles),
            current_puzzle_id=puzzles[0]["puzzle_id"],
        )
        self.repository.save_session(session)
        return session

    def get_game_session(self, session_id: str) -> SessionState:
        session = self.repository.get_session(session_id)
        if session is None:
            raise KeyError(f"SESSION_NOT_FOUND:{session_id}")
        return session

    def get_puzzle_context(self, theme_id: str, puzzle_id: str) -> dict:
        for puzzle in self._theme(theme_id).get("puzzles", []):
            if puzzle["puzzle_id"] == puzzle_id:
                return puzzle
        raise KeyError(f"PUZZLE_NOT_FOUND:{puzzle_id}")

    def get_hint_history(self, session_id: str, puzzle_id: str) -> list[HintEvent]:
        return self.repository.list_hint_events(session_id, puzzle_id)

    def get_approved_hint(self, theme_id: str, puzzle_id: str, strength: str) -> str:
        # WEAK·STRONG은 LLM의 support_need 판단 뒤 승인 데이터 경계에서 조회한다.
        # 이 함수는 강도 판단의 도메인 적절성을 재판정하지 않는다.
        try: return self._hints(theme_id)[puzzle_id][strength]
        except KeyError as exc: raise KeyError(f"APPROVED_HINT_NOT_FOUND:{theme_id}:{puzzle_id}:{strength}") from exc
    def record_hint_delivery(self, event: HintEvent) -> dict:
        # 수정 사유: 힌트 이력과 멱등성 상태를 Repository 한곳에서 관리해야
        # 메모리·PostgreSQL 구현을 바꿔도 같은 중복 방지 계약을 유지할 수 있다.
        key = event.idempotency_key
        payload = event.model_dump(mode="json")
        if key:
            stored = self.repository.get_idempotency(key)
            if stored is not None:
                stored_payload, stored_result = stored
                if stored_payload != payload:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                stored_result["deduplicated"] = True
                return stored_result

        self.repository.append_hint_event(event)
        result = {"ok": True, "deduplicated": False}
        if key:
            self.repository.save_idempotency(key, payload, result)
        return result

    def mark_puzzle_solved(self, session_id: str, puzzle_id: str) -> SessionState:
        # 수정 사유: 하나의 세션 객체로 진행 상태를 계산하고 저장해 병합 과정에서
        # 서로 다른 지역 변수명이 섞여 발생한 상태 갱신 오류를 방지한다.
        session = self.get_game_session(session_id)
        theme = self._theme(session.theme_id)
        valid = {puzzle["puzzle_id"] for puzzle in theme["puzzles"]}
        if puzzle_id not in valid:
            raise KeyError(f"PUZZLE_NOT_FOUND:{puzzle_id}")

        if puzzle_id not in session.solved_puzzle_ids:
            session.solved_puzzle_ids.append(puzzle_id)
            session.solved_puzzles = len(session.solved_puzzle_ids)

        if session.solved_puzzles >= session.total_puzzles:
            session.is_closed = True
            session.current_puzzle_id = None
        else:
            for puzzle in theme["puzzles"]:
                if puzzle["puzzle_id"] not in session.solved_puzzle_ids:
                    session.current_puzzle_id = puzzle["puzzle_id"]
                    break

        self.repository.save_session(session)
        return session

    def request_game_master(
        self,
        session_id: str,
        team_id: str,
        reason: str,
        idempotency_key: str | None = None,
    ) -> dict:
        # 수정 사유: 세션이 없거나 다른 팀의 세션이면 잘못된 운영 요청을 저장하지 않는다.
        session = self.get_game_session(session_id)
        if session.team_id != team_id:
            raise PermissionError("TEAM_SESSION_MISMATCH")
        payload = {"session_id": session_id, "team_id": team_id, "reason": reason}
        if idempotency_key:
            stored = self.repository.get_idempotency(idempotency_key)
            if stored is not None:
                stored_payload, stored_result = stored
                if stored_payload != payload:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                stored_result["deduplicated"] = True
                return stored_result
        item = {
            "request_id": str(uuid.uuid4()),
            **payload,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "status": "OPEN",
            "deduplicated": False,
        }
        self.repository.save_master_request(item)
        if idempotency_key:
            self.repository.save_idempotency(idempotency_key, payload, item)
        return item

    def report_equipment_issue(
        self,
        session_id: str,
        team_id: str,
        detail: str,
        idempotency_key: str | None = None,
    ) -> dict:
        return self.request_game_master(session_id, team_id, f"EQUIPMENT_ISSUE:{detail}", idempotency_key)

    def update_master_request(
        self,
        request_id: str,
        status: str,
        operator_id: str,
        note: str = "",
        idempotency_key: str | None = None,
    ) -> dict:
        # 수정 사유: 게임마스터 화면이 임의 상태를 덮어쓰지 않도록 허용된 전이만 코드로 제한한다.
        payload = {"request_id": request_id, "status": status, "operator_id": operator_id, "note": note}
        if idempotency_key:
            stored = self.repository.get_idempotency(idempotency_key)
            if stored is not None:
                stored_payload, stored_result = stored
                if stored_payload != payload:
                    raise ValueError("IDEMPOTENCY_CONFLICT")
                stored_result["deduplicated"] = True
                return stored_result

        item = self.repository.get_master_request(request_id)
        if item is None:
            raise KeyError(f"MASTER_REQUEST_NOT_FOUND:{request_id}")
        allowed = {
            "OPEN": {"ACKNOWLEDGED", "CANCELED"},
            "ACKNOWLEDGED": {"RESOLVED", "CANCELED"},
            "RESOLVED": set(),
            "CANCELED": set(),
        }
        current = item["status"]
        if status not in allowed.get(current, set()):
            raise ValueError(f"MASTER_REQUEST_INVALID_TRANSITION:{current}->{status}")
        item.update({
            "status": status,
            "operator_id": operator_id,
            "note": note,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "deduplicated": False,
        })
        self.repository.update_master_request(item)
        if idempotency_key:
            self.repository.save_idempotency(idempotency_key, payload, item)
        return item

    def get_master_requests(self) -> list[dict]:
        return self.repository.list_master_requests()

    def get_master_requests_for_session(
        self, session_id: str, team_id: str, limit: int = 5
    ) -> list[dict]:
        """현재 팀/세션의 최근 운영 요청만 반환한다.

        다른 팀 요청이 LLM context로 섞이지 않도록 세션 소유권을 먼저 검증한다.
        """
        session = self.get_game_session(session_id)
        if session.team_id != team_id:
            raise PermissionError("TEAM_SESSION_MISMATCH")
        items = [
            dict(item)
            for item in self.repository.list_master_requests()
            if item.get("session_id") == session_id and item.get("team_id") == team_id
        ]
        items.sort(key=lambda item: str(item.get("created_at", "")), reverse=True)
        return items[: max(limit, 0)]

    def record_conversation_turn(self, session_id: str, turn: ConversationTurn) -> None:
        # 대화 맥락은 LLM이 생략된 대상을 해석할 때만 사용하며 최근 일부만 조회한다.
        self.get_game_session(session_id)
        self.repository.append_conversation_turn(session_id, turn)

    def get_conversation_history(self, session_id: str, limit: int = 6) -> list[ConversationTurn]:
        self.get_game_session(session_id)
        return self.repository.list_conversation_turns(session_id, limit=limit)
