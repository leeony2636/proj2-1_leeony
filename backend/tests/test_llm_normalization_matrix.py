import pytest

from backend.services.llm import _normalize, inspect_raw_contract, normalization_changes


INTENTS = ["HINT", "EQUIPMENT_ISSUE", "MASTER_REQUEST", "TIME_EXTENSION_REQUEST", "UNCLEAR"]
ACTIONS = ["PROVIDE_HINT", "REQUEST_GAME_MASTER", "REPORT_EQUIPMENT", "REQUEST_TIME_EXTENSION", "ASK_CLARIFICATION"]
LOOKUPS = ["get_hint_history", "get_master_request_status"]
SUPPORT = ["STANDARD", "STRONG", "ANSWER"]
EMOTIONS = ["LOW", "MEDIUM", "HIGH"]


@pytest.mark.parametrize("case_id", range(100))
def test_llm_normalization_technical_matrix(case_id):
    """100개 합성 payload로 정규화 기술 계약만 검증한다.

    이 테스트는 실제 언어 이해/도메인 품질 평가가 아니다.
    """
    intent = INTENTS[case_id % len(INTENTS)]
    action = ACTIONS[case_id % len(ACTIONS)]
    lookup = LOOKUPS[case_id % len(LOOKUPS)]
    payload = {
        "intent": intent,
        "intents": [intent, intent],  # 중복은 제거되어야 한다.
        "actions": [action, action, "NOT_ALLOWED_ACTION"],
        "lookup_tools": [lookup, lookup, "not_allowed_lookup"],
        "emotion": EMOTIONS[case_id % len(EMOTIONS)],
        "support_need": SUPPORT[case_id % len(SUPPORT)],
        "reason": f"case-{case_id}",
        "applied_skill_rules": ["FOLLOWUP_CONTEXT"],
    }

    result = _normalize(payload, "contract-test", "fake", "2026-09-22.v3")

    assert result.intent.value == intent
    assert [item.value for item in result.intents] == [intent]
    assert [item.value for item in result.actions] == [action]
    assert [item.value for item in result.lookup_tools] == [lookup]
    assert result.prompt_version
    assert result.skill_version == "2026-09-22.v3"


def test_raw_contract_is_measured_before_normalization():
    raw = {
        "intent": "HINT",
        "intents": ["HINT", "HINT"],
        "actions": ["PROVIDE_HINT", "NOT_ALLOWED_ACTION"],
        "lookup_tools": [],
        "emotion": "LOW",
        "needs_clarification": False,
        "direct_answer_request": False,
        "strong_hint_request": False,
        "frustration_high": False,
        "support_need": "STANDARD",
        "reason": "test",
        "clarifying_question": None,
        "customer_guidance": None,
        "staff_facts": [],
        "staff_attempts": [],
        "staff_unknowns": [],
        "applied_skill_rules": [],
        "context_notes": [],
    }
    report = inspect_raw_contract(raw)
    normalized = _normalize(raw, "test", "fake", "2026-09-22.v3")
    changes = normalization_changes(raw, normalized)

    assert report["raw_contract_valid"] is False
    assert "INVALID_LIST_ENUM:actions" in report["raw_contract_errors"]
    assert "actions" in changes
    assert normalized.actions[0].value == "PROVIDE_HINT"
