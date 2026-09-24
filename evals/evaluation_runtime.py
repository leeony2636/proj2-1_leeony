"""평가 전용 격리 Runtime.

운영 데이터와 분리된 MemoryRepository를 사용하되, 참가자용 MCP 호출은 운영과
동일한 ContractDispatcher + InProcessMCPTransport + MCPClient 경로를 통과한다.
"""
from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from typing import Any, Iterator

from backend.repositories.memory import MemoryRepository
from backend.schemas import ConversationTurn, HintEvent, HintStrength
from backend.services.mcp_client import MCPClient
from backend.services.mcp_transport import InProcessMCPTransport
from backend.services.slack_notification import MockSlackNotificationAdapter
from mcp_server.adapters.local_runtime import LocalRuntime
from mcp_server.contract_dispatch import ContractDispatcher


class EvaluationMCPClient(MCPClient):
    """운영 MCPClient 인터페이스를 격리 MemoryRuntime에 그대로 연결한다."""

    def __init__(self) -> None:
        self.runtime = LocalRuntime(MemoryRepository())
        dispatcher = ContractDispatcher(self.runtime)
        super().__init__(transport=InProcessMCPTransport(dispatcher))

    # 아래 메서드는 모델 선택 공개 Tool이 아닌 서버 내부 운영 기능이다. 평가에서도
    # 동일 LocalRuntime 인터페이스를 사용하되 운영 저장소에는 접근하지 않는다.
    def list_themes(self):
        return self.runtime.list_themes()

    def create_session(self, theme_id: str, team_id: str):
        return self.runtime.create_session(theme_id, team_id).model_dump(mode="json")

    def get_session(self, session_id: str):
        return self.runtime.get_game_session(session_id).model_dump(mode="json")

    def solve(self, session_id: str, puzzle_id: str):
        return self.runtime.mark_puzzle_solved(session_id, puzzle_id).model_dump(mode="json")

    def master_requests(self):
        return self.runtime.get_master_requests()

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
        turn = ConversationTurn(
            role=role,
            content=content,
            created_at=datetime.now(timezone.utc),
            request_id=request_id,
        )
        self.runtime.record_conversation_turn(session_id, turn)
        return turn.model_dump(mode="json")

    def set_remaining_time(self, session_id: str, remaining_minutes: float) -> None:
        session = self.runtime.get_game_session(session_id)
        remaining = max(min(float(remaining_minutes), float(session.duration_minutes)), 0.0)
        elapsed = float(session.duration_minutes) - remaining
        session.started_at = datetime.now(timezone.utc) - timedelta(minutes=elapsed)
        self.runtime.repository.save_session(session)

    def set_current_puzzle(self, session_id: str, puzzle_id: str) -> None:
        session = self.runtime.get_game_session(session_id)
        self.runtime.get_puzzle_context(session.theme_id, puzzle_id)
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
                idempotency_key=f"eval-seed-hint:{session_id}:{puzzle_id}:{strength}:{len(self.runtime.get_hint_history(session_id, puzzle_id))}",
            )
        )

    def seed_master_request(self, session_id: str, team_id: str, reason: str, status: str = "OPEN") -> dict[str, Any]:
        # 평가 사전조건은 자유문자열 의미를 UNKNOWN summary로 보존한다. 실제 도메인
        # 정답을 hardcode하지 않는다.
        item = self.runtime.request_game_master(
            session_id,
            team_id,
            "UNKNOWN",
            f"eval-seed-master:{session_id}:{len(self.runtime.get_master_requests())}",
            summary=reason,
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
