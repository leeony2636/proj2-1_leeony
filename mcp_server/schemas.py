from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.schemas import MasterRequestReason


Identifier = Annotated[
    str,
    Field(
        min_length=1,
        max_length=128,
        pattern=r"^[A-Za-z0-9_-]+$",
        description="서버가 발급하거나 승인한 식별자",
    ),
]
IdempotencyKey = Annotated[
    str,
    Field(
        min_length=1,
        max_length=200,
        description="같은 쓰기 요청의 중복 처리를 막는 고유 키",
    ),
]
ReasonCode = Annotated[
    str,
    Field(min_length=1, max_length=64, pattern=r"^[A-Z0-9_:-]+$"),
]


class StrictToolModel(BaseModel):
    """MCP 경계에서 알 수 없는 입력·출력 필드를 거부한다."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ApprovedHintStrength(str, Enum):
    WEAK = "WEAK"
    STRONG = "STRONG"


class GetGameSessionInput(StrictToolModel):
    session_id: Identifier
    team_id: Identifier


class GetPuzzleContextInput(StrictToolModel):
    session_id: Identifier
    team_id: Identifier
    puzzle_id: Identifier


class GetHintHistoryInput(StrictToolModel):
    session_id: Identifier
    team_id: Identifier
    puzzle_id: Identifier
    limit: int = Field(default=20, ge=1, le=100)


class GetApprovedHintInput(StrictToolModel):
    session_id: Identifier
    team_id: Identifier
    puzzle_id: Identifier
    hint_strength: ApprovedHintStrength


class RecordHintDeliveryInput(StrictToolModel):
    session_id: Identifier
    team_id: Identifier
    puzzle_id: Identifier
    hint_strength: ApprovedHintStrength
    delivered_at: datetime
    reason_codes: list[ReasonCode] = Field(min_length=1, max_length=20)
    idempotency_key: IdempotencyKey


class RequestGameMasterInput(StrictToolModel):
    session_id: Identifier
    team_id: Identifier
    puzzle_id: Identifier | None = None
    reason: MasterRequestReason
    summary: str = Field(min_length=1, max_length=300)
    idempotency_key: IdempotencyKey


class GetMasterRequestStatusInput(StrictToolModel):
    session_id: Identifier
    team_id: Identifier
    limit: int = Field(default=5, ge=1, le=20)


class GameSessionOutput(StrictToolModel):
    session_id: Identifier
    team_id: Identifier
    theme_id: Identifier
    started_at: datetime
    duration_minutes: int = Field(ge=1)
    total_puzzles: int = Field(ge=1)
    solved_puzzles: int = Field(ge=0)
    solved_puzzle_ids: list[Identifier]
    current_puzzle_id: Identifier | None = None
    is_closed: bool


class PuzzleContextOutput(StrictToolModel):
    puzzle_id: Identifier
    order: int = Field(ge=1)
    title: str = Field(min_length=1, max_length=200)
    objective: str = Field(min_length=1, max_length=1000)
    status: str = Field(min_length=1, max_length=64)


class HintHistoryEventOutput(StrictToolModel):
    session_id: Identifier
    team_id: Identifier
    puzzle_id: Identifier
    strength: ApprovedHintStrength
    delivered_at: datetime
    reason_codes: list[ReasonCode]
    idempotency_key: str | None = None


class HintHistoryOutput(StrictToolModel):
    session_id: Identifier
    puzzle_id: Identifier
    events: list[HintHistoryEventOutput]


class ApprovedHintOutput(StrictToolModel):
    puzzle_id: Identifier
    hint_strength: ApprovedHintStrength
    hint_text: str = Field(min_length=1, max_length=2000)
    approved: Literal[True] = True


class HintDeliveryOutput(StrictToolModel):
    ok: Literal[True]
    deduplicated: bool


class GameMasterRequestOutput(StrictToolModel):
    request_id: Identifier
    session_id: Identifier
    team_id: Identifier
    reason: MasterRequestReason
    summary: str = Field(min_length=1, max_length=300)
    created_at: datetime
    status: Literal["OPEN", "ACKNOWLEDGED", "RESOLVED", "CANCELED"]
    deduplicated: bool
    operator_id: str | None = None
    note: str = ""
    updated_at: datetime | None = None
    legacy_reason_unmapped: bool = False


class GameMasterRequestStatusOutput(StrictToolModel):
    requests: list[GameMasterRequestOutput]
