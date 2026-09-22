from contextlib import contextmanager

from backend.services.langfuse_service import build_observation, record_event


def test_observation_allowlist_removes_answers_hints_tokens_and_transcripts():
    event = build_observation(
        "hint_delivered",
        {
            "request_id": "req-1",
            "session_id": "session-1",
            "team_id": "team-secret",
            "puzzle_id": "train-p01",
            "status": "PROVIDE_HINT",
            "hint_text": "정답에 가까운 승인 힌트",
            "answer": "SECRET_ANSWER",
            "offer_id": "offer-secret",
            "transcript": "고객의 음성 전사",
            "reason_codes": ["DEFAULT_WEAK"],
            "llm_provider": "baseline",
        },
    )

    dumped = event.model_dump(mode="json", exclude_none=True)
    assert dumped["request_id"] == "req-1"
    assert dumped["team_id_hash"]
    assert "team-secret" not in dumped["team_id_hash"]
    assert "hint_text" not in dumped
    assert "answer" not in dumped
    assert "offer_id" not in dumped
    assert "transcript" not in dumped


def test_record_event_sends_only_safe_observation_to_langfuse(monkeypatch):
    calls = []

    class FakeObservation:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class FakeLangfuse:
        def start_as_current_observation(self, **kwargs):
            calls.append(kwargs)
            return FakeObservation()

        def flush(self):
            calls.append({"flushed": True})

    monkeypatch.setenv("LANGFUSE_PUBLIC_KEY", "public-test")
    monkeypatch.setenv("LANGFUSE_SECRET_KEY", "secret-test")
    monkeypatch.setattr("backend.services.langfuse_service.Langfuse", lambda **_: FakeLangfuse())

    record_event(
        "hint_delivered",
        {
            "request_id": "req-2",
            "session_id": "session-2",
            "puzzle_id": "train-p01",
            "status": "PROVIDE_HINT",
            "hint_text": "숨겨야 하는 힌트",
            "answer": "숨겨야 하는 정답",
        },
    )

    observation = calls[0]
    assert observation["name"] == "agent.hint_delivered"
    assert observation["output"]["status"] == "PROVIDE_HINT"
    assert "hint_text" not in observation["output"]
    assert "answer" not in observation["output"]
    assert calls[-1] == {"flushed": True}
