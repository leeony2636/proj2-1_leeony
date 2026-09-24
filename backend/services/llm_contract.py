"""LLM 원본 출력 전용 strict 계약.

FastAPI 고객 입력, MCP 입력/출력, 저장 모델과 분리한다. 이 모듈의 목적은
모델이 반환한 JSON의 형식/타입을 검증하는 것이며 도메인 판단의 정답 여부를
증명하지 않는다.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from backend.schemas import (
    AgentActionType,
    EmotionSignal,
    IntentResult,
    IntentType,
    LookupToolType,
    SupportNeed,
)

IntentLiteral = Literal["HINT", "EQUIPMENT_ISSUE", "MASTER_REQUEST", "TIME_EXTENSION_REQUEST", "UNCLEAR"]
ActionLiteral = Literal[
    "PROVIDE_HINT",
    "REQUEST_GAME_MASTER",
    "REPORT_EQUIPMENT",
    "REQUEST_TIME_EXTENSION",
    "ASK_CLARIFICATION",
]
LookupLiteral = Literal["get_hint_history", "get_master_request_status"]
EmotionLiteral = Literal["LOW", "MEDIUM", "HIGH"]
SupportLiteral = Literal["STANDARD", "STRONG", "ANSWER"]


class LLMRawOutput(BaseModel):
    """모델이 반환해야 하는 원본 JSON 계약.

    실행 의미에 영향을 주는 필드는 모두 필수다. ``strict=True``와
    ``extra='forbid'``로 문자열 boolean, 숫자→문자열, 미지 필드 등의
    자동 변환/무시를 막는다.
    """

    model_config = ConfigDict(strict=True, extra="forbid")

    intent: IntentLiteral
    intents: list[IntentLiteral]
    actions: list[ActionLiteral]
    lookup_tools: list[LookupLiteral]
    emotion: EmotionLiteral
    needs_clarification: bool
    clarifying_question: str | None
    reason: str = Field(min_length=1, max_length=500)
    direct_answer_request: bool
    strong_hint_request: bool
    frustration_high: bool
    support_need: SupportLiteral
    customer_guidance: str | None
    staff_facts: list[str] = Field(max_length=8)
    staff_attempts: list[str] = Field(max_length=8)
    staff_unknowns: list[str] = Field(max_length=8)
    applied_skill_rules: list[str] = Field(max_length=8)
    context_notes: list[str] = Field(max_length=8)


@dataclass(frozen=True)
class ContractErrorDetail:
    loc: str
    error_type: str

    def as_dict(self) -> dict[str, str]:
        return {"loc": self.loc, "type": self.error_type}


class LLMContractError(ValueError):
    error_code = "LLM_CONTRACT_ERROR"


class LLMJSONParseError(LLMContractError):
    error_code = "LLM_JSON_PARSE_ERROR"


class LLMSchemaValidationError(LLMContractError):
    error_code = "LLM_SCHEMA_VALIDATION_ERROR"

    def __init__(self, details: list[ContractErrorDetail]):
        self.details = details
        super().__init__(self.error_code)


class LLMPolicyValidationError(LLMContractError):
    error_code = "LLM_POLICY_VALIDATION_ERROR"

    def __init__(self, codes: list[str]):
        self.codes = codes
        super().__init__(self.error_code)


def safe_validation_errors(exc: ValidationError) -> list[ContractErrorDetail]:
    """민감한 입력값을 제외하고 필드 위치와 오류 종류만 반환한다."""

    details: list[ContractErrorDetail] = []
    for item in exc.errors(include_input=False, include_url=False):
        loc = ".".join(str(part) for part in item.get("loc", ())) or "$"
        details.append(ContractErrorDetail(loc=loc, error_type=str(item.get("type", "validation_error"))))
    return details


def validate_llm_schema(data: Any) -> LLMRawOutput:
    try:
        return LLMRawOutput.model_validate(data, strict=True)
    except ValidationError as exc:
        raise LLMSchemaValidationError(safe_validation_errors(exc)) from exc


def validate_confirmed_policy(model: LLMRawOutput) -> None:
    """확정된 필드 관계만 검사한다.

    미확정 시간/진도 규칙, 재요청 자동 STRONG 등은 여기에서 만들지 않는다.
    현재 확정된 관계는 '추가 질문 필요'라고 선언했으면 실제 질문 문자열이
    존재해야 한다는 계약뿐이다.
    """

    errors: list[str] = []
    if model.needs_clarification and not (model.clarifying_question or "").strip():
        errors.append("CLARIFICATION_QUESTION_REQUIRED")
    if errors:
        raise LLMPolicyValidationError(errors)


def to_intent_result(
    model: LLMRawOutput,
    *,
    provider: str,
    model_name: str,
    prompt_version: str,
    skill_version: str | None,
) -> IntentResult:
    """검증된 값만 기존 내부 IntentResult로 옮긴다. 의미 보정은 하지 않는다."""

    return IntentResult(
        intent=IntentType(model.intent),
        intents=[IntentType(value) for value in model.intents],
        actions=[AgentActionType(value) for value in model.actions],
        lookup_tools=[LookupToolType(value) for value in model.lookup_tools],
        emotion=EmotionSignal(model.emotion),
        needs_clarification=model.needs_clarification,
        clarifying_question=model.clarifying_question,
        reason=model.reason,
        direct_answer_request=model.direct_answer_request,
        strong_hint_request=model.strong_hint_request,
        frustration_high=model.frustration_high,
        support_need=SupportNeed(model.support_need),
        customer_guidance=model.customer_guidance,
        staff_facts=list(model.staff_facts),
        staff_attempts=list(model.staff_attempts),
        staff_unknowns=list(model.staff_unknowns),
        applied_skill_rules=list(model.applied_skill_rules),
        context_notes=list(model.context_notes),
        provider=provider,
        model=model_name,
        prompt_version=prompt_version,
        skill_version=skill_version,
    )
