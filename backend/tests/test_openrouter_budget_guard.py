import json

import pytest

from backend.services.llm import _openrouter_decision
from evals.run_llm_eval import run


def test_live_openrouter_run_is_blocked_without_phase_cost_cap(tmp_path):
    output = tmp_path / "no-budget.json"
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")

    report = run(
        dataset,
        "openrouter",
        output,
        allow_external_llm=True,
        max_cost_usd=None,
    )

    assert report["status"] == "NOT_RUN_INVALID_OR_MISSING_COST_CAP"
    assert json.loads(output.read_text(encoding="utf-8"))["results"] == []


def test_phase_cost_cap_cannot_exceed_global_project_limit(tmp_path):
    output = tmp_path / "over-budget.json"
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")

    report = run(
        dataset,
        "openrouter",
        output,
        allow_external_llm=True,
        max_cost_usd=30.01,
    )

    assert report["status"] == "NOT_RUN_INVALID_OR_MISSING_COST_CAP"
    assert report["phase_budget_ceiling_usd"] == 30
    assert report["project_budget_reference_usd"] == 30



def test_model_selection_phase_cannot_exceed_five_dollars(tmp_path):
    output = tmp_path / "selection-over-budget.json"
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")

    report = run(
        dataset,
        "openrouter",
        output,
        allow_external_llm=True,
        max_cost_usd=5.01,
        phase="model_selection",
    )

    assert report["status"] == "NOT_RUN_INVALID_OR_MISSING_COST_CAP"
    assert report["phase_budget_ceiling_usd"] == 5.0

def test_runner_stops_before_requests_when_api_key_is_absent(tmp_path, monkeypatch):
    output = tmp_path / "missing-key.json"
    dataset = tmp_path / "dataset.jsonl"
    dataset.write_text("{}\n", encoding="utf-8")
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
    monkeypatch.setenv("OPENROUTER_MODEL", "vendor/model")

    report = run(
        dataset,
        "openrouter",
        output,
        allow_external_llm=True,
        max_cost_usd=1,
    )

    assert report["status"] == "NOT_RUN_API_KEY_MISSING"
    assert json.loads(output.read_text(encoding="utf-8"))["results"] == []


def test_provider_does_not_fall_back_to_an_unspecified_free_model(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-only")
    monkeypatch.delenv("OPENROUTER_MODEL", raising=False)

    with pytest.raises(RuntimeError, match="OPENROUTER_MODEL_REQUIRED"):
        _openrouter_decision(stage="INITIAL", payload={}, skill_version=None)
