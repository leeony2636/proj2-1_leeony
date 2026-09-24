import copy
import hashlib
import json
from datetime import datetime, timezone

from backend.services import langfuse_service as lf
from evals.model_selection_scorecard import HUMAN_AXES, build_scorecard, final_contract_status
from evals.score_reviewed_results import score_reviewed, publish_reviewed, write_review_csv
from evals.quality_approval import inspect_quality_approval
from evals import run_llm_eval


def test_langfuse_case_event_and_score_share_trace_without_raw_content(monkeypatch):
    calls = []

    class Span:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            return False

    class Client:
        def start_as_current_observation(self, **kwargs):
            calls.append(("observation", kwargs))
            return Span()

        def create_score(self, **kwargs):
            calls.append(("score", kwargs))

        def flush(self):
            pass

    monkeypatch.setattr(lf, "_get_client", lambda: Client())
    seed = "eval_test_run_1"
    assert lf.record_event("evaluation_case", {
        "trace_id": seed, "evaluation_run_id": "run1", "evaluation_case_id": 1,
        "dataset_sha256": "hash", "llm_model": "test/model", "quality_status": "REVIEW_REQUIRED",
        "utterance": "SECRET_USER_TEXT", "hint_text": "SECRET_HINT", "review_evidence": "SECRET_EVIDENCE",
    })
    assert lf.record_evaluation_score(
        trace_seed=seed, name="structured_output_stability", value=1.0,
        evaluation_started_at=datetime.now(timezone.utc).isoformat(),
        evaluation_run_id="run1", case_id=1, dataset_sha256="hash", model="test/model",
    )
    obs, score = calls[0][1], calls[1][1]
    assert obs["trace_context"]["trace_id"] == score["trace_id"] == lf.trace_id_for_seed(seed)
    assert obs["output"]["evaluation_case_id"] == "1"
    assert not any(secret in str(obs) or secret in str(score) for secret in (
        "SECRET_USER_TEXT", "SECRET_HINT", "SECRET_EVIDENCE"
    ))
    assert len(score["score_id"]) == 32


def test_nested_prompt_profile_cannot_export_raw_text():
    observation = lf.build_observation("llm_call", {
        "prompt_profile": {
            "component_chars": {"user_message": 42, "raw_message": "SECRET"},
            "raw_prompt": "SECRET", "component_tokens_estimated": {"domain_skill": 20},
        },
    }).model_dump(mode="json", exclude_none=True)
    assert "SECRET" not in str(observation)
    assert observation["prompt_profile"]["component_chars"]["user_message"] == 42


def test_scorecard_keeps_semantics_pending_and_uses_final_contract():
    audit = [
        {"stage": "LLM_CONTRACT", "llm_stage": "INITIAL", "normalized_contract_valid": False},
        {"stage": "LLM_CONTRACT", "llm_stage": "INITIAL", "normalized_contract_valid": True},
        {"stage": "INITIAL_DECISION", "actions": ["A"]},
    ]
    card = build_scorecard(
        provider="openrouter", execution_status="COMPLETED", audit=audit,
        case_evaluation={"quality_contract_gate": {"status": "PASS"}}, metrics={},
    )
    assert final_contract_status(audit, "openrouter", "COMPLETED") == "PASS"
    assert card["structured_output_stability"]["status"] == "PASS"
    assert card["domain_judgment"]["status"] == "PENDING_REVIEW"
    assert card["observation_interpretation"]["status"] == "NOT_APPLICABLE"


def _reviewed_document():
    summary = {
        "evaluation_run_id": "run1", "dataset_sha256": "dataset_hash",
        "quality_contract_sha256": "contract_hash", "model": "model/id",
        "evaluation_started_at": datetime.now(timezone.utc).isoformat(),
        "observability_complete": True, "completed_rows": 30, "failed_rows": 0,
        "hard_fail_auto_cases": 0,
    }
    results = []
    for case_id in range(1, 31):
        seed = f"eval_run1_{case_id}"
        card = {
            "structured_output_stability": {"status": "PASS"},
            "observation_interpretation": {"status": "PENDING_REVIEW"},
            "review_record": {
                "status": "REVIEWED", "reviewer": "team-member",
                "ratings": {axis: "PASS" for axis in HUMAN_AXES},
                "evidence": {axis: "case-specific checked reason" for axis in HUMAN_AXES},
                "hard_fail_triggered": False, "hard_fail_evidence": "",
            },
        }
        results.append({
            "id": case_id, "evaluation_run_id": "run1", "dataset_sha256": "dataset_hash",
            "quality_contract_sha256": "contract_hash", "model": "model/id",
            "trace_seed": seed, "langfuse_trace_id": lf.trace_id_for_seed(seed),
            "execution_status": "COMPLETED", "quality_contract_gate": {"status": "REVIEW_REQUIRED"},
            "project_model_capability_scorecard": card,
        })
    return {"summary": summary, "results": results}


def test_reviewed_gate_requires_all_30_complete_and_pass():
    document = _reviewed_document()
    assert score_reviewed(document)["status"] == "QUALITY_PASS"
    pending = copy.deepcopy(document)
    pending["results"][0]["project_model_capability_scorecard"]["review_record"]["evidence"]["tool_judgment"] = ""
    assert score_reviewed(pending)["status"] == "AWAITING_REVIEW"
    partial = copy.deepcopy(document)
    partial["results"][0]["project_model_capability_scorecard"]["review_record"]["ratings"]["domain_judgment"] = "PARTIAL"
    assert score_reviewed(partial)["status"] == "QUALITY_FAIL"
    wrong_trace = copy.deepcopy(document)
    wrong_trace["results"][0]["langfuse_trace_id"] = "wrong"
    assert score_reviewed(wrong_trace)["status"] == "INVALID"


def test_review_publish_sends_only_numeric_scores(monkeypatch):
    document = _reviewed_document()
    calls = []
    monkeypatch.setattr("evals.score_reviewed_results.record_evaluation_score", lambda **kwargs: calls.append(kwargs) or True)
    monkeypatch.setattr("evals.score_reviewed_results.record_event", lambda *args: calls.append(args) or True)
    assert publish_reviewed(document, score_reviewed(document))
    assert len(calls) == 30 * len(HUMAN_AXES) + 1
    assert not any("case-specific checked reason" in str(call) for call in calls)


def test_review_csv_omits_raw_evidence(tmp_path):
    document = _reviewed_document()
    path = tmp_path / "reviewed.csv"
    write_review_csv(path, document, score_reviewed(document))
    content = path.read_text(encoding="utf-8-sig")
    assert content.count("run1") >= 30
    assert "case-specific checked reason" not in content
    assert "domain_judgment" in content


def test_quality_approval_requires_current_hash_and_independent_signoff(tmp_path):
    dataset = tmp_path / "dataset.jsonl"
    contract = tmp_path / "quality.json"
    approval = tmp_path / "approval.json"
    dataset.write_text("case", encoding="utf-8")
    contract.write_text("contract", encoding="utf-8")
    document = {
        "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        "quality_contract_sha256": hashlib.sha256(contract.read_bytes()).hexdigest(),
        "approval_status": "PENDING_TEAM_REVIEW", "reviewer": "", "approval_evidence": "",
        "approved_case_ids": [],
    }
    approval.write_text(json.dumps(document), encoding="utf-8")
    assert inspect_quality_approval(approval, dataset, contract)["status"] == "PENDING"
    document.update({"approval_status": "APPROVED", "reviewer": "teammate", "approval_evidence": "D4 meeting record", "approved_case_ids": list(range(1, 31))})
    approval.write_text(json.dumps(document), encoding="utf-8")
    assert inspect_quality_approval(approval, dataset, contract)["status"] == "PASS"
    contract.write_text("changed contract", encoding="utf-8")
    assert inspect_quality_approval(approval, dataset, contract)["status"] == "PENDING"


def test_evaluation_stops_after_first_case_if_langfuse_export_fails(monkeypatch, tmp_path):
    monkeypatch.setattr(run_llm_eval, "record_event", lambda *_: False)
    monkeypatch.setattr(run_llm_eval, "record_evaluation_score", lambda **_: True)
    summary = run_llm_eval.run(
        run_llm_eval.ROOT / "evals/dataset.jsonl", "baseline", tmp_path / "stopped.json",
        limit=2, allow_observability_export=True, csv_output=tmp_path / "safe.csv",
    )
    assert summary["status"] == "STOPPED_LANGFUSE_EXPORT_FAILED"
    assert summary["observability_complete"] is False
    assert summary["completed_rows"] == 1
    assert summary["csv_export_complete"] is True
    assert "response" not in (tmp_path / "safe.csv").read_text(encoding="utf-8-sig")
