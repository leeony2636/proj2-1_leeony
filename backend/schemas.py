from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    HINT = "HINT"
    EQUIPMENT_ISSUE = "EQUIPMENT_ISSUE"
    MASTER_REQUEST = "MASTER_REQUEST"
    UNCLEAR = "UNCLEAR"


class AgentStatus(str, Enum):
    NEED_MORE_INFO = "NEED_MORE_INFO"
    PROVIDE_HINT = "PROVIDE_HINT"
    MASTER_REQUEST = "MASTER_REQUEST"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


class HintStrength(str, Enum):
    WEAK = "WEAK"
    STRONG = "STRONG"
    # 기존 데이터 호환용. 최신 자동 판정에서는 사용하지 않는다.
    NORMAL = "NORMAL"


class EmotionSignal(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


class CreateSessionRequest(BaseModel):
    theme_id: str
    team_id: str


class SessionState(BaseModel):
    session_id: str
    team_id: str
    theme_id: str
    started_at: datetime
    duration_minutes: int
    total_puzzles: int
    solved_puzzles: int = 0
    solved_puzzle_ids: list[str] = Field(default_factory=list)
    current_puzzle_id: str | None = None
    is_closed: bool = False

    @property
    def remaining_puzzles(self) -> int:
        return max(self.total_puzzles - self.solved_puzzles, 0)

    @property
    def remaining_puzzle_ratio(self) -> float:
        return 0.0 if self.total_puzzles <= 0 else self.remaining_puzzles / self.total_puzzles

    @property
    def solved_puzzle_ratio(self) -> float:
        return 0.0 if self.total_puzzles <= 0 else self.solved_puzzles / self.total_puzzles


class HintEvent(BaseModel):
    session_id: str
    team_id: str
    puzzle_id: str
    strength: HintStrength
    delivered_at: datetime
    reason_codes: list[str] = Field(default_factory=list)


class AgentRequest(BaseModel):
    session_id: str
    team_id: str
    message: str
    puzzle_id: str | None = None
    user_id: str | None = None


class IntentResult(BaseModel):
    intent: IntentType
    emotion: EmotionSignal = EmotionSignal.LOW
    needs_clarification: bool = False
    reason: str = ""
    recommended_tools: list[str] = Field(default_factory=list)

    # 최신 기획안의 차별화 포인트를 구조화한다.
    direct_answer_request: bool = False
    strong_hint_request: bool = False
    frustration_high: bool = False

    provider: str = "baseline"
    model: str = "baseline"


class HintDecision(BaseModel):
    strength: HintStrength
    reason_codes: list[str]
    remaining_time_minutes: float
    remaining_puzzles: int
    remaining_puzzle_ratio: float
    solved_puzzle_ratio: float


class AgentResponse(BaseModel):
    status: AgentStatus
    session_id: str
    team_id: str
    puzzle_id: str | None = None
    intent: IntentType | None = None
    emotion: EmotionSignal | None = None
    hint_strength: HintStrength | None = None
    hint_text: str | None = None

    # 데모에서 "LLM이 최종 판정을 하지 않는다"는 사실을 보이기 위한 필드.
    decision_source: str | None = None
    spoiler_guard: str = "ANSWERVAULT_SEPARATED"

    # STRONG 이후 사용자가 직접 눌렀을 때만 정답 경로를 연다.
    answer_available: bool = False
    answer_reveal_url: str | None = None

    # 내부 판정에 필요한 시간만 남기고, 퍼즐 개수/비율은 고객 응답에 노출하지 않는다.
    remaining_time_minutes: float | None = None

    reason_codes: list[str] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)
    llm_provider: str | None = None
    llm_model: str | None = None
    next_action: str | None = None


class SolvePuzzleRequest(BaseModel):
    puzzle_id: str
