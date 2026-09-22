from __future__ import annotations

from datetime import datetime
from enum import Enum
import uuid
from typing import Literal

from pydantic import BaseModel, Field


class IntentType(str, Enum):
    HINT = "HINT"
    EQUIPMENT_ISSUE = "EQUIPMENT_ISSUE"
    MASTER_REQUEST = "MASTER_REQUEST"
    UNCLEAR = "UNCLEAR"


class AgentStatus(str, Enum):
    NEED_MORE_INFO = "NEED_MORE_INFO"
    PROVIDE_HINT = "PROVIDE_HINT"
    ANSWER_CONFIRMATION_REQUIRED = "ANSWER_CONFIRMATION_REQUIRED"
    MASTER_REQUEST = "MASTER_REQUEST"
    CLOSED = "CLOSED"
    ERROR = "ERROR"


class MasterRequestStatus(str, Enum):
    OPEN = "OPEN"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    CANCELED = "CANCELED"


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
    # P0 LocalRuntime의 재전송 중복 방지용 키. PostgreSQL 전환 시 UNIQUE 제약으로 이동한다.
    idempotency_key: str | None = None


class AgentRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req_{uuid.uuid4().hex}")
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
    # 정답 직접 요구인 경우 STRONG 힌트와 분리된 일회성 동의 토큰을 반환한다.
    # 일반 STRONG 힌트 자체는 자동 제공하며 정답 문자열은 이 응답에 포함하지 않는다.
    offer_id: str | None = None
    offer_expires_at: datetime | None = None
    requires_confirmation: bool = False

    # 데모에서 "LLM이 최종 판정을 하지 않는다"는 사실을 보이기 위한 필드.
    decision_source: str | None = None
    spoiler_guard: str = "ANSWERVAULT_SEPARATED"

    # 내부 판정에 필요한 시간만 남기고, 퍼즐 개수/비율은 고객 응답에 노출하지 않는다.
    remaining_time_minutes: float | None = None

    reason_codes: list[str] = Field(default_factory=list)
    selected_tools: list[str] = Field(default_factory=list)
    llm_provider: str | None = None
    llm_model: str | None = None
    next_action: str | None = None


class AnswerConfirmationRequest(BaseModel):
    session_id: str
    team_id: str
    puzzle_id: str
    offer_id: str


class AnswerResponse(BaseModel):
    puzzle_id: str
    answer: str
    policy: str


class STTRequest(BaseModel):
    audio_bytes: bytes
    content_type: str
    language: str = "ko-KR"
    max_duration_ms: int = Field(default=15_000, ge=1)


class STTResult(BaseModel):
    transcript: str
    confidence: float = Field(ge=0.0, le=1.0)
    language: str
    duration_ms: int = Field(ge=0)
    provider: str
    model: str
    request_id: str = Field(default_factory=lambda: f"stt_{uuid.uuid4().hex}")


class STTAgentResponse(BaseModel):
    status: Literal["ACCEPTED", "CONFIRMATION_REQUIRED", "RETRY_REQUIRED"]
    transcript: str | None = None
    confidence: float | None = None
    reason_codes: list[str] = Field(default_factory=list)
    stt_request_id: str | None = None
    agent_response: AgentResponse | None = None


class MasterRequestActionRequest(BaseModel):
    operator_id: str = Field(min_length=1)
    note: str = ""
    idempotency_key: str | None = None


class SolvePuzzleRequest(BaseModel):
    puzzle_id: str
