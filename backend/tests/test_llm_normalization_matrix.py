import copy

import pytest

from backend.services.llm import _normalize, inspect_raw_contract, normalization_changes
from backend.services.llm_contract import LLMSchemaValidationError


INTENTS = ["HINT", "EQUIPMENT_ISSUE", "MASTER_REQUEST", "TIME_EXTENSION_REQUEST", "UNCLEAR"]
ACTIONS = ["PROVIDE_HINT", "REQUEST_GAME_MASTER", "REPORT_EQUIPMENT", "REQUEST_TIME_EXTENSION", "ASK_CLARIFICATION"]
LOOKUPS = ["get_hint_history", "get_master_request_status"]
SUPPORT = ["STANDARD", "STRONG", "ANSWER"]
EMOTIONS = ["LOW", "MEDIUM", "HIGH"]


def _valid_payload(case_id: int = 0) -> dict:
    intent = INTENTS[case_id % len(INTENTS)]
    action = ACTIONS[case_id % len(ACTIONS)]
    lookup = LOOKUPS[case_id % len(LOOKUPS)]
    return {
        "intent": intent,
        "intents": [intent],
        "actions": [action],
        "lookup_tools": [lookup],
        "emotion": EMOTIONS[case_id % len(EMOTIONS)],
        "needs_clarification": False,
        "clarifying_question": None,
        "reason": f"case-{case_id}",
        "direct_answer_request": False,
        "strong_hint_request": False,
        "frustration_high": False,
        "support_need": SUPPORT[case_id % len(SUPPORT)],
        "customer_guidance": None,
        "staff_facts": [],
        "staff_attempts": [],
        "staff_unknowns": [],
        "applied_skill_rules": [],
        "context_notes": [],
    }


@pytest.mark.parametrize("case_id", range(100))
def test_llm_strict_contract_accepts_valid_payload_without_semantic_normalization(case_id):
    """합성 100건으로 strict 형식 계약을 확인한다.

    실제 한국어 이해나 도메인 품질 점수가 아니라 형식/타입 계약 테스트다.
    """
    payload = _valid_payload(case_id)
    result = _normalize(payload, "contract-test", "fake", "2026-09-22.v3")

    assert result.intent.value == payload["intent"]
    assert [item.value for item in result.intents] == payload["intents"]
    assert [item.value for item in result.actions] == payload["actions"]
    assert [item.value for item in result.lookup_tools] == payload["lookup_tools"]
    assert normalization_changes(payload, result) == []


@pytest.mark.parametrize(
    ("mutator", "expected_loc"),
    [
        (lambda p: p.__setitem__("intent", "NOT_AN_INTENT"), "intent"),
        (lambda p: p.__setitem__("actions", ["NOT_ALLOWED_ACTION"]), "actions.0"),
        (lambda p: p.__setitem__("lookup_tools", ["not_allowed_lookup"]), "lookup_tools.0"),
        (lambda p: p.__setitem__("needs_clarification", "false"), "needs_clarification"),
        (lambda p: p.pop("support_need"), "support_need"),
        (lambda p: p.__setitem__("unexpected_field", "x"), "unexpected_field"),
    ],
)
def test_invalid_execution_affecting_fields_are_rejected_not_fixed(mutator, expected_loc):
    payload = _valid_payload()
    mutator(payload)

    report = inspect_raw_contract(payload)
    assert report["raw_contract_valid"] is False
    assert report["contract_error_kind"] == "SCHEMA"
    assert any(item["loc"] == expected_loc for item in report["raw_contract_errors"])
    with pytest.raises(LLMSchemaValidationError):
        _normalize(payload, "contract-test", "fake", "2026-09-22.v3")


def test_string_false_is_not_coerced_to_true():
    payload = _valid_payload()
    payload["direct_answer_request"] = "false"
    with pytest.raises(LLMSchemaValidationError):
        _normalize(payload, "contract-test", "fake", "2026-09-22.v3")


def test_raw_contract_does_not_silently_drop_invalid_action():
    payload = _valid_payload()
    payload["actions"] = ["PROVIDE_HINT", "NOT_ALLOWED_ACTION"]

    report = inspect_raw_contract(payload)
    assert report["raw_contract_valid"] is False
    assert report["contract_error_kind"] == "SCHEMA"
    assert any(item["loc"] == "actions.1" for item in report["raw_contract_errors"])
