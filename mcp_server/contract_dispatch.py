"""운영 MCP 도구의 단일 Pydantic/권한 contract dispatcher."""
from __future__ import annotations

from typing import Any

from backend.schemas import HintEvent
from mcp_server.adapters.local_runtime import LocalRuntime
from mcp_server.schemas import (
    ApprovedHintOutput,
    GameMasterRequestOutput,
    GameMasterRequestStatusOutput,
    GameSessionOutput,
    GetApprovedHintInput,
    GetGameSessionInput,
    GetHintHistoryInput,
    GetMasterRequestStatusInput,
    GetPuzzleContextInput,
    HintDeliveryOutput,
    HintHistoryOutput,
    PuzzleContextOutput,
    RecordHintDeliveryInput,
    RequestGameMasterInput,
)


class ContractDispatcher:
    """FastMCP와 격리 평가가 공유하는 실제 도구 계약 실행기."""

    def __init__(self, runtime: LocalRuntime | None = None) -> None:
        self.runtime = runtime or LocalRuntime()

    def _validate_session_owner(self, session_id: str, team_id: str, *, allow_closed: bool = False):
        session = self.runtime.get_game_session(session_id)
        if session.team_id != team_id:
            raise PermissionError("TEAM_SESSION_MISMATCH")
        if session.is_closed and not allow_closed:
            raise PermissionError("SESSION_CLOSED")
        return session

    def _validate_current_puzzle(self, session_id: str, team_id: str, puzzle_id: str):
        session = self._validate_session_owner(session_id, team_id)
        if session.current_puzzle_id != puzzle_id:
            raise PermissionError("PUZZLE_SEQUENCE_MISMATCH")
        return session

    def dispatch(self, name: str, payload: dict[str, Any]) -> dict[str, Any]:
        if name == "get_game_session":
            data = GetGameSessionInput.model_validate(payload)
            session = self._validate_session_owner(data.session_id, data.team_id, allow_closed=True)
            return GameSessionOutput.model_validate(session.model_dump(mode="json")).model_dump(mode="json")

        if name == "get_puzzle_context":
            data = GetPuzzleContextInput.model_validate(payload)
            session = self._validate_current_puzzle(data.session_id, data.team_id, data.puzzle_id)
            puzzle = self.runtime.get_puzzle_context(session.theme_id, data.puzzle_id)
            return PuzzleContextOutput.model_validate(puzzle).model_dump(mode="json")

        if name == "get_hint_history":
            data = GetHintHistoryInput.model_validate(payload)
            self._validate_current_puzzle(data.session_id, data.team_id, data.puzzle_id)
            history = self.runtime.get_hint_history(data.session_id, data.puzzle_id)
            return HintHistoryOutput(
                session_id=data.session_id,
                puzzle_id=data.puzzle_id,
                events=[item.model_dump(mode="json") for item in reversed(history[-data.limit :])],
            ).model_dump(mode="json")

        if name == "get_approved_hint":
            data = GetApprovedHintInput.model_validate(payload)
            session = self._validate_current_puzzle(data.session_id, data.team_id, data.puzzle_id)
            text = self.runtime.get_approved_hint(session.theme_id, data.puzzle_id, data.hint_strength.value)
            return ApprovedHintOutput(
                puzzle_id=data.puzzle_id,
                hint_strength=data.hint_strength,
                hint_text=text,
            ).model_dump(mode="json")

        if name == "record_hint_delivery":
            data = RecordHintDeliveryInput.model_validate(payload)
            self._validate_current_puzzle(data.session_id, data.team_id, data.puzzle_id)
            event = HintEvent(
                session_id=data.session_id,
                team_id=data.team_id,
                puzzle_id=data.puzzle_id,
                strength=data.hint_strength.value,
                delivered_at=data.delivered_at,
                reason_codes=list(data.reason_codes),
                idempotency_key=data.idempotency_key,
            )
            return HintDeliveryOutput.model_validate(
                self.runtime.record_hint_delivery(event)
            ).model_dump(mode="json")

        if name == "request_game_master":
            data = RequestGameMasterInput.model_validate(payload)
            if data.puzzle_id is not None:
                self._validate_current_puzzle(data.session_id, data.team_id, data.puzzle_id)
            else:
                self._validate_session_owner(data.session_id, data.team_id, allow_closed=True)
            result = self.runtime.request_game_master(
                data.session_id,
                data.team_id,
                data.reason.value,
                data.idempotency_key,
                summary=data.summary,
            )
            return GameMasterRequestOutput.model_validate(result).model_dump(mode="json")

        if name == "get_master_request_status":
            data = GetMasterRequestStatusInput.model_validate(payload)
            self._validate_session_owner(data.session_id, data.team_id, allow_closed=True)
            rows = self.runtime.get_master_requests_for_session(data.session_id, data.team_id, data.limit)
            return GameMasterRequestStatusOutput(
                requests=[GameMasterRequestOutput.model_validate(row) for row in rows]
            ).model_dump(mode="json")

        raise KeyError(f"MCP_TOOL_NOT_FOUND:{name}")


MODEL_SELECTABLE_TOOLS = frozenset({"get_hint_history", "get_master_request_status"})
_DEFAULT_DISPATCHER = ContractDispatcher()


def dispatch_tool(name: str, input_data: dict[str, Any]) -> dict[str, Any]:
    return _DEFAULT_DISPATCHER.dispatch(name, input_data)
