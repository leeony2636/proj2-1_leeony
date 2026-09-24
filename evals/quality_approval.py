"""Reviewer sign-off gate for the fixed core-30 evaluator contract."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def inspect_quality_approval(
    approval_path: Path,
    dataset_path: Path,
    quality_contract_path: Path,
    required_cases: int = 30,
) -> dict[str, Any]:
    if not approval_path.is_file():
        return {"status": "PENDING", "reason": "APPROVAL_FILE_MISSING", "approved_cases": 0}
    try:
        document = json.loads(approval_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"status": "INVALID", "reason": "APPROVAL_FILE_INVALID", "approved_cases": 0}
    if not isinstance(document, dict):
        return {"status": "INVALID", "reason": "APPROVAL_OBJECT_REQUIRED", "approved_cases": 0}
    ids = document.get("approved_case_ids")
    valid_ids = (
        isinstance(ids, list)
        and all(isinstance(case_id, int) and not isinstance(case_id, bool) for case_id in ids)
        and len(ids) == required_cases
        and set(ids) == set(range(1, required_cases + 1))
    )
    checks = {
        "dataset_hash_matches": document.get("dataset_sha256") == _sha256(dataset_path),
        "quality_contract_hash_matches": document.get("quality_contract_sha256") == _sha256(quality_contract_path),
        "reviewer_recorded": bool(str(document.get("reviewer") or "").strip()),
        "approval_evidence_recorded": bool(str(document.get("approval_evidence") or "").strip()),
        "all_cases_approved": valid_ids,
        "status_approved": document.get("approval_status") == "APPROVED",
    }
    return {
        "status": "PASS" if all(checks.values()) else "PENDING",
        "checks": checks,
        "approved_cases": len(ids) if isinstance(ids, list) else 0,
        "approval_file": str(approval_path),
    }
