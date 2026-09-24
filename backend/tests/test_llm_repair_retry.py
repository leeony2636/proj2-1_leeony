import json
import sys
from types import SimpleNamespace

import pytest

from backend.services import llm


def _valid_output():
    return {
        "intent": "HINT",
        "intents": ["HINT"],
        "actions": ["PROVIDE_HINT"],
        "lookup_tools": [],
        "emotion": "LOW",
        "needs_clarification": False,
        "clarifying_question": None,
        "reason": "사용자가 힌트를 요청했습니다.",
        "direct_answer_request": False,
        "strong_hint_request": False,
        "frustration_high": False,
        "support_need": "STANDARD",
        "customer_guidance": None,
        "staff_facts": [],
        "staff_attempts": [],
        "staff_unknowns": [],
        "applied_skill_rules": [],
        "context_notes": [],
    }


def _response(content):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10, total_tokens=30),
    )


def _install_fake_provider(monkeypatch, outputs):
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            return _response(outputs[len(calls) - 1])

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    monkeypatch.setenv("OPENROUTER_MODEL", "test/model")
    events = []
    monkeypatch.setattr(llm, "record_event", lambda name, payload: events.append((name, payload)))
    return calls, events


def _decision(calls_audit):
    return llm._openrouter_decision(
        stage="INITIAL",
        payload={"message": "힌트 주세요", "context": {"untrusted": True}},
        skill_version="test-skill-v1",
        request_id="request-test",
        audit=calls_audit,
    )


def test_contract_error_gets_exactly_one_evidence_based_repair(monkeypatch):
    invalid = _valid_output()
    invalid["actions"] = ["NOT_ALLOWED"]
    calls, events = _install_fake_provider(
        monkeypatch,
        [json.dumps(invalid), json.dumps(_valid_output(), ensure_ascii=False)],
    )
    audit = []

    result = _decision(audit)

    assert result.intent.value == "HINT"
    assert len(calls) == 2
    assert calls[0]["response_format"] == {"type": "json_object"}
    assert calls[0]["extra_body"]["provider"] == {"zdr": True, "data_collection": "deny"}
    assert calls[1]["extra_body"]["provider"] == {"zdr": True, "data_collection": "deny"}
    assert calls[1]["messages"][0]["content"] == llm.REPAIR_SYSTEM_PROMPT
    repair_input = json.loads(calls[1]["messages"][1]["content"])
    assert repair_input["original_request"]["message"] == "힌트 주세요"
    assert repair_input["validation_failure"]["kind"] == "SCHEMA"
    assert any(item.get("strategy") == "REPAIR" for item in audit)
    assert any(item.get("terminal_state") == "REPAIRED" for item in audit)
    assert sum(name == "llm_call" for name, _ in events) == 2
    assert sum(name == "llm_retry" for name, _ in events) == 1
    assert sum(item["stage"] == "LLM_PROVIDER_CALL" and item["zdr_required"] for item in audit) == 2


def test_invalid_repair_terminates_as_fail_without_third_call(monkeypatch):
    invalid = _valid_output()
    invalid["actions"] = ["NOT_ALLOWED"]
    calls, _ = _install_fake_provider(
        monkeypatch,
        [json.dumps(invalid), json.dumps(invalid)],
    )
    audit = []

    with pytest.raises(llm.LLMSchemaValidationError):
        _decision(audit)

    assert len(calls) == 2
    assert any(item.get("terminal_state") == "FAIL" for item in audit)
    assert not any(item.get("terminal_state") == "REPAIRED" for item in audit)


def test_repair_prompt_does_not_include_unbounded_invalid_output(monkeypatch):
    invalid = _valid_output()
    invalid["actions"] = ["NOT_ALLOWED"]
    calls, _ = _install_fake_provider(
        monkeypatch,
        ["{" + ("x" * 10000), json.dumps(_valid_output())],
    )

    _decision([])

    repair_input = json.loads(calls[1]["messages"][1]["content"])
    assert len(repair_input["invalid_output"]) == 4000
