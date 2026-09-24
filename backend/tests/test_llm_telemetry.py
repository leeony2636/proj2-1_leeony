import json
import sys
from types import SimpleNamespace

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
        "reason": "조회 결과를 반영했습니다.",
        "direct_answer_request": False,
        "strong_hint_request": False,
        "frustration_high": False,
        "support_need": "STANDARD",
        "customer_guidance": None,
        "staff_facts": [],
        "staff_attempts": [],
        "staff_unknowns": [],
        "applied_skill_rules": [],
        "context_notes": ["tool history used"],
    }


def test_openrouter_usage_and_followup_replay_are_audited(monkeypatch):
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            usage = SimpleNamespace(
                prompt_tokens=120,
                completion_tokens=40,
                total_tokens=160,
                prompt_tokens_details=SimpleNamespace(cached_tokens=20, cache_write_tokens=5),
                completion_tokens_details=SimpleNamespace(reasoning_tokens=12),
                cost=0.00123,
            )
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(_valid_output(), ensure_ascii=False)))],
                usage=usage,
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    monkeypatch.setattr(llm, "record_event", lambda *args, **kwargs: True)

    audit = []
    payload = {
        "message": "아까 힌트에서 조금 더 알려줘",
        "context": {
            "domain_skill": {"version": "test"},
            "recent_turns": [{"role": "assistant", "message": "이전 힌트"}],
            "tool_results": [{"tool": "get_hint_history", "status": "OK"}],
            "session_id": "session-1",
        },
        "previous_decision": {"lookup_tools": ["get_hint_history"]},
        "instruction": "조회 결과를 반영해 다시 판단",
    }

    llm._openrouter_decision(
        stage="FOLLOWUP_AFTER_TOOLS",
        payload=payload,
        skill_version="test-skill-v1",
        request_id="request-test",
        session_id="session-1",
        audit=audit,
    )

    assert len(calls) == 1
    assert calls[0]["extra_body"]["provider"] == {"zdr": True, "data_collection": "deny"}
    assert calls[0]["extra_body"]["usage"] == {"include": True}

    provider_call = next(item for item in audit if item.get("stage") == "LLM_PROVIDER_CALL")
    assert provider_call["input_tokens"] == 120
    assert provider_call["output_tokens"] == 40
    assert provider_call["reasoning_tokens"] == 12
    assert provider_call["cached_tokens"] == 20
    assert provider_call["cache_write_tokens"] == 5
    assert provider_call["cost_usd"] == 0.00123
    assert provider_call["context_replayed"] is True
    assert provider_call["previous_decision_included"] is True
    assert provider_call["tool_results_included"] is True
    profile = provider_call["prompt_profile"]
    assert profile["provider_input_tokens_actual"] == 120
    assert profile["estimate_basis"] == "PROPORTIONAL_TO_CHAR_COUNT_FROM_PROVIDER_INPUT_TOKENS"
    assert profile["component_tokens_estimated"]["domain_skill"] is not None
    assert profile["component_tokens_estimated"]["tool_results"] is not None


def test_openrouter_request_applies_price_cap_when_configured(monkeypatch):
    calls = []

    class FakeCompletions:
        def create(self, **kwargs):
            calls.append(kwargs)
            usage = SimpleNamespace(prompt_tokens=10, completion_tokens=5, total_tokens=15, cost=0.0001)
            return SimpleNamespace(
                choices=[SimpleNamespace(message=SimpleNamespace(content=json.dumps(_valid_output(), ensure_ascii=False)))],
                usage=usage,
            )

    class FakeOpenAI:
        def __init__(self, **kwargs):
            self.chat = SimpleNamespace(completions=FakeCompletions())

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")
    monkeypatch.setenv("OPENROUTER_MAX_PROMPT_PRICE_PER_M", "1.0")
    monkeypatch.setenv("OPENROUTER_MAX_COMPLETION_PRICE_PER_M", "5.0")
    monkeypatch.setattr(llm, "record_event", lambda *args, **kwargs: True)

    llm._openrouter_decision(stage="INITIAL", payload={"message": "테스트", "context": {}}, skill_version="test")

    assert calls[0]["extra_body"]["provider"]["max_price"] == {
        "prompt": 1.0,
        "completion": 5.0,
    }
