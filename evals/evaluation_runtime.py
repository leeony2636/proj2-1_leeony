"""평가 전용 격리 Runtime.

운영 Repository/MCP 상태를 건드리지 않고, 소스 데이터 파일은 읽기만 하며 모든 세션·힌트·
운영 요청·대화 기록을 새 MemoryRepository에 저장한다. 외부 Slack 전송도 Mock만 사용한다.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from backend.repositories.memory import MemoryRepository
from backend.schemas import ConversationTurn, HintEvent, HintStrength, SessionState
from backend.services.slack_notification import MockSlackNotificationAdapter
from mcp_server.adapters.local_runtime import LocalRuntime


class EvaluationMCPClient:
    """MCPClient와 같은 최소 인터페이스를 평가용 LocalRuntime에 연결한다."""

    def __init__(self) -> None:
        self.runtime = LocalRuntime(MemoryRepository())

    def list_themes(self):
        return self.runtime.list_themes()

    def create_session(self, theme_id: str, team_id: str):
        return self.runtime.create_session(theme_id, team_id).model_dump(mode="json")

    def get_session(self, session_id: str):
        return self.runtime.get_game_session(session_id).model_dump(mode="json")

    def solve(self, session_id: str, puzzle_id: str):
        return self.runtime.mark_puzzle_solved(session_id, puzzle_id).model_dump(mode="json")

    def get_puzzle(self, theme_id: str, puzzle_id: str):
        return self.runtime.get_puzzle_context(theme_id, puzzle_id)

    def get_history(self, session_id: str, puzzle_id: str):
        return [item.model_dump(mode="json") for item in self.runtime.get_hint_history(session_id, puzzle_id)]

    def get_hint(self, theme_id: str, puzzle_id: str, strength: str):
        return self.runtime.get_approved_hint(theme_id, puzzle_id, strength)

    def record_hint(self, event: HintEvent):
        return self.runtime.record_hint_delivery(event)

    def call_master(self, session_id: str, team_id: str, reason: str, idempotency_key: str | None = None):
        return self.runtime.request_game_master(session_id, team_id, reason, idempotency_key)

    def equipment(self, session_id: str, team_id: str, detail: str, idempotency_key: str | None = None):
        return self.runtime.report_equipment_issue(session_id, team_id, detail, idempotency_key)

    def master_requests(self):
        return self.runtime.get_master_requests()

    def master_request_status(self, session_id: str, team_id: str, limit: int = 5):
        return self.runtime.get_master_requests_for_session(session_id, team_id, limit)

    def update_master_request(
        self,
        request_id: str,
        status: str,
        operator_id: str,
        note: str = "",
        idempotency_key: str | None = None,
    ):
        return self.runtime.update_master_request(request_id, status, operator_id, note, idempotency_key)

    def get_conversation_history(self, session_id: str, limit: int = 6):
        return self.runtime.get_conversation_history(session_id, limit)

    def record_conversation_turn(self, session_id: str, role: str, content: str, request_id: str | None = None):
        return self.runtime.record_conversation_turn(
            session_id,
            ConversationTurn(
                role=role,
                content=content,
                created_at=datetime.now(timezone.utc),
                request_id=request_id,
            ),
        )

    def set_remaining_time(self, session_id: str, remaining_minutes: float) -> None:
        session = self.runtime.get_game_session(session_id)
        remaining = max(min(float(remaining_minutes), float(session.duration_minutes)), 0.0)
        elapsed = float(session.duration_minutes) - remaining
        session.started_at = datetime.now(timezone.utc) - timedelta(minutes=elapsed)
        self.runtime.repository.save_session(session)

    def set_current_puzzle(self, session_id: str, puzzle_id: str) -> None:
        session = self.runtime.get_game_session(session_id)
        self.runtime.get_puzzle_context(session.theme_id, puzzle_id)  # 존재 검증
        session.current_puzzle_id = puzzle_id
        self.runtime.repository.save_session(session)

    def seed_hint(self, session_id: str, team_id: str, puzzle_id: str, strength: str, reason: str = "EVAL_SEED") -> None:
        self.runtime.record_hint_delivery(
            HintEvent(
                session_id=session_id,
                team_id=team_id,
                puzzle_id=puzzle_id,
                strength=HintStrength(strength),
                delivered_at=datetime.now(timezone.utc),
                reason_codes=[reason],
                idempotency_key=f"eval-seed-hint:{session_id}:{puzzle_id}:{strength}:{len(self.get_history(session_id, puzzle_id))}",
            )
        )

    def seed_master_request(self, session_id: str, team_id: str, reason: str, status: str = "OPEN") -> dict[str, Any]:
        item = self.runtime.request_game_master(
            session_id,
            team_id,
            reason,
            f"eval-seed-master:{session_id}:{len(self.runtime.get_master_requests())}",
        )
        if status == "ACKNOWLEDGED":
            item = self.runtime.update_master_request(item["request_id"], "ACKNOWLEDGED", "eval-operator")
        elif status == "RESOLVED":
            self.runtime.update_master_request(item["request_id"], "ACKNOWLEDGED", "eval-operator")
            item = self.runtime.update_master_request(item["request_id"], "RESOLVED", "eval-operator")
        elif status == "CANCELED":
            item = self.runtime.update_master_request(item["request_id"], "CANCELED", "eval-operator")
        elif status != "OPEN":
            raise ValueError(f"EVAL_MASTER_STATUS_UNSUPPORTED:{status}")
        return item


@contextmanager
def isolated_agent_runtime() -> Iterator[EvaluationMCPClient]:
    """Agent와 AnswerVault가 같은 평가용 Memory Runtime을 보도록 잠시 교체한다."""
    from backend.services import agent_orchestrator, answer_vault

    client = EvaluationMCPClient()
    old_agent_mcp = agent_orchestrator.mcp
    old_answer_mcp = answer_vault.mcp
    old_slack = agent_orchestrator.slack_notification_adapter
    try:
        agent_orchestrator.mcp = client
        answer_vault.mcp = client
        agent_orchestrator.slack_notification_adapter = MockSlackNotificationAdapter()
        yield client
    finally:
        agent_orchestrator.mcp = old_agent_mcp
        answer_vault.mcp = old_answer_mcp
        agent_orchestrator.slack_notification_adapter = old_slack
