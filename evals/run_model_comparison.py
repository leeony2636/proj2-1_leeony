"""4모델 비교 실행 전 정본/평가계약/하드코딩 누수를 fail-closed로 검증한다.

이 파일은 네트워크/유료 호출을 하지 않는다. 실제 4모델 실행은 run_model_selection.py가 담당한다.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

# 로컬 VS Code/PowerShell 실행 시 .env를 읽되, 이미 설정된 환경변수는 덮어쓰지 않는다.
load_dotenv(ROOT / ".env", override=False)

from evals.audit_runtime_hardcoding import audit_runtime
from evals.quality_approval import inspect_quality_approval



def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"INVALID_JSON_OBJECT:{path}")
    return data


def _load_rows(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"INVALID_JSONL:{line_no}") from exc
        rows.append(row)
    return rows


def offline_preflight(
    dataset: Path,
    *,
    policy_path: Path = Path("evals/model_selection_policy.json"),
    quality_contract_path: Path = Path("evals/core30_quality_contract.json"),
    approval_path: Path = Path("evals/quality_contract_approval.json"),
) -> dict[str, Any]:
    rows = _load_rows(dataset)
    policy = _load_json(policy_path)
    contract = _load_json(quality_contract_path)
    ids = [row.get("id") for row in rows]
    counts = Counter(str(row.get("category")) for row in rows)
    errors: list[str] = []
    warnings: list[str] = []

    required_cases = int(policy.get("required_case_count", 30))
    if len(rows) != required_cases:
        errors.append(f"ROW_COUNT:{len(rows)}")
    if len(set(ids)) != len(ids):
        errors.append("DUPLICATE_CASE_ID")
    if sorted(ids) != list(range(1, required_cases + 1)):
        errors.append(f"CASE_ID_RANGE_NOT_1_TO_{required_cases}")
    expected_categories = {"normal": 10, "boundary": 12, "failure": 8}
    if dict(counts) != expected_categories:
        errors.append(f"CATEGORY_COUNTS:{dict(counts)}")

    missing_human = [row.get("id") for row in rows if row.get("human_validated") is not True]
    if missing_human:
        errors.append(f"HUMAN_VALIDATED_MISSING:{missing_human}")
    missing_reviewer = [row.get("id") for row in rows if not str(row.get("reviewer", "")).strip()]
    if missing_reviewer:
        errors.append(f"REVIEWER_MISSING:{missing_reviewer}")

    dataset_sha = _sha256(dataset)
    if policy.get("dataset_sha256") != dataset_sha:
        errors.append("POLICY_DATASET_HASH_MISMATCH")
    if contract.get("dataset_sha256") != dataset_sha:
        errors.append("QUALITY_CONTRACT_DATASET_HASH_MISMATCH")

    contract_cases = contract.get("cases") if isinstance(contract.get("cases"), dict) else {}
    human_review_case_ids = [
        int(case_id) for case_id, case in contract_cases.items()
        if isinstance(case, dict) and case.get("human_review_required") is True
    ]
    fully_automatic_case_ids = [
        int(case_id) for case_id, case in contract_cases.items()
        if isinstance(case, dict) and case.get("human_review_required") is not True
    ]
    missing_review_descriptions = [
        int(case_id) for case_id, case in contract_cases.items()
        if isinstance(case, dict) and case.get("human_review_required") is True
        and not str(case.get("expected_description", "")).strip()
    ]
    if missing_review_descriptions:
        errors.append(f"HUMAN_REVIEW_DESCRIPTION_MISSING:{missing_review_descriptions}")

    missing_contract_cases = [case_id for case_id in ids if str(case_id) not in contract_cases]
    extra_contract_cases = [key for key in contract_cases if key not in {str(case_id) for case_id in ids}]
    if missing_contract_cases:
        errors.append(f"QUALITY_CONTRACT_MISSING:{missing_contract_cases}")
    if extra_contract_cases:
        errors.append(f"QUALITY_CONTRACT_EXTRA:{extra_contract_cases}")

    # 문장상 과거 상태가 필요한 3/4번은 실제 fixture도 함께 있어야 FOLLOWUP 판단을 검증할 수 있다.
    by_id = {int(row["id"]): row for row in rows}
    case3_setup = by_id.get(3, {}).get("eval_setup") or {}
    case4_setup = by_id.get(4, {}).get("eval_setup") or {}
    if not case3_setup.get("master_requests"):
        errors.append("CASE_3_EXISTING_MASTER_REQUEST_FIXTURE_MISSING")
    if not case4_setup.get("hint_history"):
        errors.append("CASE_4_HINT_HISTORY_FIXTURE_MISSING")

    hardcoding = audit_runtime(dataset)
    if hardcoding["status"] != "PASS":
        errors.append("RUNTIME_HARDCODING_AUDIT_FAILED")

    if float(policy.get("model_selection_total_budget_usd", 0)) != 5.0:
        errors.append("MODEL_SELECTION_BUDGET_NOT_5_USD")
    if int(policy.get("required_model_count", 0)) != 4:
        errors.append("MODEL_COUNT_NOT_4")
    fixed = policy.get("fixed_generation_settings") or {}
    if fixed.get("temperature") != 0 or fixed.get("max_output_tokens") != 850:
        warnings.append("GENERATION_SETTINGS_DIFFER_FROM_CURRENT_LLM_DEFAULTS")

    approval = inspect_quality_approval(approval_path, dataset, quality_contract_path, required_cases)

    return {
        "status": "PASS" if not errors else "FAIL",
        "offline_only": True,
        "network_attempted": False,
        "dataset": str(dataset),
        "dataset_sha256": dataset_sha,
        "quality_contract_sha256": _sha256(quality_contract_path),
        "policy_sha256": _sha256(policy_path),
        "rows": len(rows),
        "unique_ids": len(set(ids)),
        "categories": dict(counts),
        "human_validated_missing": missing_human,
        "reviewer_missing": missing_reviewer,
        "quality_contract_human_review_required_count": len(human_review_case_ids),
        "quality_contract_human_review_case_ids": sorted(human_review_case_ids),
        "quality_contract_fully_automatic_count": len(fully_automatic_case_ids),
        "quality_contract_fully_automatic_case_ids": sorted(fully_automatic_case_ids),
        "hardcoding_audit": hardcoding,
        "contract_approval": approval,
        "official_paid_run_ready": not errors and approval["status"] == "PASS",
        "errors": errors,
        "warnings": warnings,
        "note": "이 preflight는 유료 호출 없이 core-30 정본·평가계약·runtime 누수를 검사한다.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/dataset.jsonl")
    parser.add_argument("--policy", default="evals/model_selection_policy.json")
    parser.add_argument("--quality-contract", default="evals/core30_quality_contract.json")
    parser.add_argument("--approval", default="evals/quality_contract_approval.json")
    parser.add_argument("--offline-only", action="store_true")
    args = parser.parse_args()

    report = offline_preflight(
        Path(args.dataset),
        policy_path=Path(args.policy),
        quality_contract_path=Path(args.quality_contract),
        approval_path=Path(args.approval),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
