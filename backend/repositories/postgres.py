from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import json
from pathlib import Path
from threading import Lock
from typing import Any, Iterator

from backend.schemas import ConversationTurn, HintEvent, SessionState


ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = ROOT / "backend" / "db" / "schema.sql"


def normalize_dsn(database_url: str) -> str:
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


class PostgresRepository:
    """B안 PostgreSQL 저장소.

    psycopg는 메서드 호출 시 지연 import해 P0 memory 모드에서 DB 패키지가 없어도
    Agent가 시작되도록 한다. 실제 운영 전에는 연결·마이그레이션·복구 테스트가 필요하다.
    """

    def __init__(self, database_url: str, schema_path: Path = SCHEMA_PATH) -> None:
        if not database_url:
            raise ValueError("DATABASE_URL_REQUIRED")
        self.dsn = normalize_dsn(database_url)
        self.schema_path = schema_path
        self._schema_initialized = False
        self._schema_lock = Lock()

    def _connect(self):
        try:
            import psycopg
            from psycopg.rows import dict_row
        except ImportError as exc:  # pragma: no cover - P0 memory 모드에서는 실행하지 않음
            raise RuntimeError("PSYCOPG_NOT_INSTALLED") from exc
        return psycopg.connect(self.dsn, row_factory=dict_row)

    @contextmanager
    def _connection(self) -> Iterator[Any]:
        connection = self._connect()
        try:
            if not self._schema_initialized:
                with self._schema_lock:
                    if not self._schema_initialized:
                        connection.execute(self.schema_path.read_text(encoding="utf-8"))
                        connection.commit()
                        self._schema_initialized = True
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _session_row(session: SessionState) -> tuple:
        return (
            session.session_id,
            session.team_id,
            session.theme_id,
            session.started_at,
            session.duration_minutes,
            session.total_puzzles,
            session.solved_puzzles,
            json.dumps(session.solved_puzzle_ids),
            session.current_puzzle_id,
            session.is_closed,
        )

    @staticmethod
    def _to_session(row: dict) -> SessionState:
        return SessionState(
            session_id=row["session_id"],
            team_id=row["team_id"],
            theme_id=row["theme_id"],
            started_at=row["started_at"],
            duration_minutes=row["duration_minutes"],
            total_puzzles=row["total_puzzles"],
            solved_puzzles=row["solved_puzzles"],
            solved_puzzle_ids=row["solved_puzzle_ids"],
            current_puzzle_id=row["current_puzzle_id"],
            is_closed=row["is_closed"],
        )

    def save_session(self, session: SessionState) -> None:
        sql = """
            INSERT INTO sessions
            (session_id, team_id, theme_id, started_at, duration_minutes, total_puzzles,
             solved_puzzles, solved_puzzle_ids, current_puzzle_id, is_closed)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            ON CONFLICT (session_id) DO UPDATE SET
              team_id=EXCLUDED.team_id, theme_id=EXCLUDED.theme_id,
              started_at=EXCLUDED.started_at, duration_minutes=EXCLUDED.duration_minutes,
              total_puzzles=EXCLUDED.total_puzzles, solved_puzzles=EXCLUDED.solved_puzzles,
              solved_puzzle_ids=EXCLUDED.solved_puzzle_ids,
              current_puzzle_id=EXCLUDED.current_puzzle_id, is_closed=EXCLUDED.is_closed
        """
        with self._connection() as connection:
            connection.execute(sql, self._session_row(session))

    def get_session(self, session_id: str) -> SessionState | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM sessions WHERE session_id=%s", (session_id,)
            ).fetchone()
        return self._to_session(row) if row else None

    def append_hint_event(self, event: HintEvent) -> None:
        sql = """
            INSERT INTO hint_events
            (session_id, team_id, puzzle_id, strength, delivered_at, reason_codes, idempotency_key)
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s)
            ON CONFLICT (idempotency_key) DO NOTHING
        """
        with self._connection() as connection:
            connection.execute(sql, (
                event.session_id, event.team_id, event.puzzle_id, event.strength.value,
                event.delivered_at, json.dumps(event.reason_codes), event.idempotency_key,
            ))

    def list_hint_events(self, session_id: str, puzzle_id: str) -> list[HintEvent]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM hint_events WHERE session_id=%s AND puzzle_id=%s ORDER BY event_id",
                (session_id, puzzle_id),
            ).fetchall()
        return [HintEvent(
            session_id=row["session_id"], team_id=row["team_id"], puzzle_id=row["puzzle_id"],
            strength=row["strength"], delivered_at=row["delivered_at"],
            reason_codes=row["reason_codes"], idempotency_key=row["idempotency_key"],
        ) for row in rows]

    def get_idempotency(self, key: str) -> tuple[dict, dict] | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT payload, result FROM idempotency_records WHERE idempotency_key=%s", (key,)
            ).fetchone()
        return (row["payload"], row["result"]) if row else None

    def save_idempotency(self, key: str, payload: dict, result: dict) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO idempotency_records(idempotency_key, payload, result)
                   VALUES (%s, %s::jsonb, %s::jsonb)
                   ON CONFLICT (idempotency_key) DO NOTHING""",
                (key, json.dumps(payload), json.dumps(result)),
            )

    def save_master_request(self, request: dict) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO master_requests
                   (request_id, session_id, team_id, reason, created_at, status, operator_id, note, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
                (
                    request["request_id"], request["session_id"], request["team_id"],
                    # 기존 단일 reason 컬럼과의 쓰기 호환. 물리 migration 전에는
                    # ``ENUM:summary``로 저장하고 읽기 계층이 다시 분리한다.
                    f"{request['reason']}:{request.get('summary', request['reason'])}",
                    request["created_at"], request["status"],
                    request.get("operator_id"), request.get("note", ""), request.get("updated_at"),
                ),
            )

    def get_master_request(self, request_id: str) -> dict | None:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM master_requests WHERE request_id=%s", (request_id,)
            ).fetchone()
        return dict(row) if row else None

    def update_master_request(self, request: dict) -> None:
        with self._connection() as connection:
            connection.execute(
                """UPDATE master_requests SET status=%s, operator_id=%s, note=%s, updated_at=%s
                   WHERE request_id=%s""",
                (
                    request["status"], request.get("operator_id"), request.get("note", ""),
                    request.get("updated_at"), request["request_id"],
                ),
            )

    def list_master_requests(self) -> list[dict]:
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM master_requests ORDER BY created_at"
            ).fetchall()
        return [dict(row) for row in rows]

    def append_conversation_turn(self, session_id: str, turn: ConversationTurn) -> None:
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO conversation_turns(session_id, role, content, created_at, request_id)
                   VALUES (%s, %s, %s, %s, %s)""",
                (session_id, turn.role, turn.content, turn.created_at, turn.request_id),
            )

    def list_conversation_turns(self, session_id: str, limit: int = 6) -> list[ConversationTurn]:
        with self._connection() as connection:
            rows = connection.execute(
                """SELECT role, content, created_at, request_id
                   FROM conversation_turns WHERE session_id=%s
                   ORDER BY turn_id DESC LIMIT %s""",
                (session_id, max(limit, 0)),
            ).fetchall()
        rows = list(reversed(rows))
        return [ConversationTurn(**dict(row)) for row in rows]
