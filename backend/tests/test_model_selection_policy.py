from pathlib import Path

from evals.audit_runtime_hardcoding import audit_runtime
from evals.run_model_comparison import offline_preflight
from evals.run_model_selection import run_selection


ROOT = Path(__file__).resolve().parents[2]


def test_core30_offline_preflight_has_full_quality_contract_and_no_runtime_leakage():
    report = offline_preflight(
        ROOT / "evals/dataset.jsonl",
        policy_path=ROOT / "evals/model_selection_policy.json",
        quality_contract_path=ROOT / "evals/core30_quality_contract.json",
    )

    assert report["status"] == "PASS"
    assert report["rows"] == 30
    assert report["hardcoding_audit"]["status"] == "PASS"


def test_runtime_hardcoding_audit_does_not_find_core30_literals_in_production_runtime():
    report = audit_runtime(ROOT / "evals/dataset.jsonl")
    assert report["status"] == "PASS"
    assert report["violations"] == []


def test_four_model_selection_budget_is_capped_at_five_dollars_before_network():
    report = run_selection(
        dataset=ROOT / "evals/dataset.jsonl",
        policy_path=ROOT / "evals/model_selection_policy.json",
        quality_contract_path=ROOT / "evals/core30_quality_contract.json",
        candidate_path=ROOT / "evals/model_candidates.example.json",
        output_dir=ROOT / "evals/results/live_runs/test-model-selection",
        explicit_models="vendor/a,vendor/b,vendor/c,vendor/d",
        budget_usd=5.01,
        allow_external_llm=False,
        allow_observability_export=False,
        confirm_dedicated_key_cap=False,
    )

    assert report["status"] == "NOT_RUN_SELECTION_BUDGET_INVALID"
    assert report["configured_max_usd"] == 5.0


def test_model_selection_requires_exactly_four_models_before_external_call():
    report = run_selection(
        dataset=ROOT / "evals/dataset.jsonl",
        policy_path=ROOT / "evals/model_selection_policy.json",
        quality_contract_path=ROOT / "evals/core30_quality_contract.json",
        candidate_path=ROOT / "evals/model_candidates.example.json",
        output_dir=ROOT / "evals/results/live_runs/test-model-selection",
        explicit_models="vendor/a,vendor/b,vendor/c",
        budget_usd=5.0,
        allow_external_llm=False,
        allow_observability_export=False,
        confirm_dedicated_key_cap=False,
    )

    assert report["status"] == "NOT_RUN_MODEL_COUNT_MISMATCH"
    assert report["required_model_count"] == 4


def test_catalog_price_estimate_is_marked_as_estimate_not_actual():
    from evals.run_model_selection import _estimate_cost_from_catalog

    summary = {
        "token_totals": {"input_tokens": 1000, "output_tokens": 200},
        "provider_call_count": 2,
    }
    estimate = _estimate_cost_from_catalog(
        summary,
        {"prompt": "0.000001", "completion": "0.000002", "request": "0"},
    )

    assert estimate["estimated_cost_usd"] == 0.0014
    assert estimate["estimate_source"] == "ZDR_CATALOG_PRICING_X_ACTUAL_TOKENS"
    assert estimate["estimated_cost_complete"] is True


def test_official_model_selection_requires_langfuse_export_before_network(monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "test-key-not-printed")
    report = run_selection(
        dataset=ROOT / "evals/dataset.jsonl",
        policy_path=ROOT / "evals/model_selection_policy.json",
        quality_contract_path=ROOT / "evals/core30_quality_contract.json",
        candidate_path=ROOT / "evals/model_candidates.example.json",
        output_dir=ROOT / "evals/results/live_runs/test-model-selection",
        explicit_models="vendor/a,vendor/b,vendor/c,vendor/d",
        budget_usd=5.0,
        allow_external_llm=True,
        allow_observability_export=False,
        confirm_dedicated_key_cap=True,
    )

    assert report["status"] == "NOT_RUN_LANGFUSE_REQUIRED"
    assert report["runs"] == []
