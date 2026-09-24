"""core-30으로 OpenRouter 후보 4개를 동일 조건에서 비교하는 공식 모델선정 runner.

보안/비용/정본 검사를 모두 통과하기 전에는 유료 inference를 시작하지 않는다.
평가 정답/quality contract는 Agent 입력에 전달하지 않고 응답 생성 후 채점에만 사용한다.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from typing import Any
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

# 로컬 VS Code/PowerShell 실행 시 .env를 읽되, 이미 설정된 환경변수는 덮어쓰지 않는다.
load_dotenv(ROOT / ".env", override=False)

from backend.services.langfuse_service import observability_auth_check, observability_configured, record_event
from evals.openrouter_zdr_preflight import check_zdr_eligibility, fetch_zdr_catalog, parse_model_ids
from evals.run_llm_eval import run as run_model_eval
from evals.run_model_comparison import offline_preflight



def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"INVALID_JSON_OBJECT:{path}")
    return data




def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _estimate_cost_from_catalog(
    summary: dict[str, Any],
    pricing: dict[str, Any] | None,
) -> dict[str, Any]:
    """OpenRouter catalog 가격과 실제 token/call 수로 참고 예상 비용을 계산한다.

    실제 청구는 Provider가 반환한 cost를 기준으로 하며, catalog pricing 누락 시 추정하지 않는다.
    """
    pricing = pricing or {}
    prompt_rate = _as_float(pricing.get("prompt"))
    completion_rate = _as_float(pricing.get("completion"))
    request_rate = _as_float(pricing.get("request"))
    tokens = summary.get("token_totals") if isinstance(summary.get("token_totals"), dict) else {}
    input_tokens = tokens.get("input_tokens")
    output_tokens = tokens.get("output_tokens")
    calls = summary.get("provider_call_count")

    components: dict[str, float] = {}
    if prompt_rate is not None and isinstance(input_tokens, int):
        components["prompt"] = input_tokens * prompt_rate
    if completion_rate is not None and isinstance(output_tokens, int):
        components["completion"] = output_tokens * completion_rate
    if request_rate is not None and isinstance(calls, int):
        components["request"] = calls * request_rate
    if not components:
        return {
            "estimated_cost_usd": None,
            "estimated_cost_complete": False,
            "estimate_source": "CATALOG_PRICING_UNAVAILABLE",
        }
    required_parts = []
    if isinstance(input_tokens, int):
        required_parts.append(prompt_rate is not None)
    if isinstance(output_tokens, int):
        required_parts.append(completion_rate is not None)
    # request fee가 없는 모델은 0 또는 미제공일 수 있어 필수로 강제하지 않는다.
    return {
        "estimated_cost_usd": round(sum(components.values()), 8),
        "estimated_cost_complete": bool(required_parts and all(required_parts)),
        "estimate_source": "ZDR_CATALOG_PRICING_X_ACTUAL_TOKENS",
        "estimate_components_usd": {key: round(value, 8) for key, value in components.items()},
    }


def _candidate_ids(candidate_path: Path, explicit_models: str | None) -> list[str]:
    # 우선순위: CLI --models > .env OPENROUTER_MODELS > candidate JSON.
    raw_models = (explicit_models or os.getenv("OPENROUTER_MODELS", "")).strip()
    if raw_models:
        return parse_model_ids(raw_models)
    data = _load_json(candidate_path)
    candidates = data.get("candidates") if isinstance(data.get("candidates"), list) else []
    ids = [str(item.get("exact_model_id") or "").strip() for item in candidates if isinstance(item, dict)]
    if any(not model for model in ids):
        missing = [item.get("slot") for item in candidates if isinstance(item, dict) and not str(item.get("exact_model_id") or "").strip()]
        raise ValueError(f"EXACT_MODEL_ID_REQUIRED_FOR_SLOTS:{missing}")
    return parse_model_ids(",".join(ids))


def run_selection(
    *,
    dataset: Path,
    policy_path: Path,
    quality_contract_path: Path,
    candidate_path: Path,
    output_dir: Path,
    explicit_models: str | None,
    budget_usd: float | None,
    allow_external_llm: bool,
    allow_observability_export: bool,
    confirm_dedicated_key_cap: bool,
    approval_path: Path = Path("evals/quality_contract_approval.json"),
    csv_output_dir: Path = Path("evals/results/model_selection_csv"),
) -> dict[str, Any]:
    policy = _load_json(policy_path)
    configured_budget = float(policy.get("model_selection_total_budget_usd", 5.0))
    env_budget = os.getenv("MODEL_SELECTION_BUDGET_USD", "").strip()
    if budget_usd is not None:
        requested_budget = float(budget_usd)
    elif env_budget:
        requested_budget = float(env_budget)
    else:
        requested_budget = configured_budget

    preflight = offline_preflight(
        dataset, policy_path=policy_path, quality_contract_path=quality_contract_path,
        approval_path=approval_path,
    )
    if preflight["status"] != "PASS":
        return {"status": "NOT_RUN_OFFLINE_PREFLIGHT_FAILED", "preflight": preflight, "runs": []}

    try:
        models = _candidate_ids(candidate_path, explicit_models)
    except Exception as exc:
        return {"status": "NOT_RUN_MODEL_LIST_INVALID", "error": str(exc), "runs": []}

    required_models = int(policy.get("required_model_count", 4))
    if len(models) != required_models:
        return {
            "status": "NOT_RUN_MODEL_COUNT_MISMATCH",
            "required_model_count": required_models,
            "actual_model_count": len(models),
            "models": models,
            "runs": [],
        }
    if requested_budget <= 0 or requested_budget > configured_budget:
        return {
            "status": "NOT_RUN_SELECTION_BUDGET_INVALID",
            "requested_budget_usd": requested_budget,
            "configured_max_usd": configured_budget,
            "runs": [],
        }
    if not allow_external_llm:
        return {
            "status": "NOT_RUN_EXTERNAL_LLM_APPROVAL_REQUIRED",
            "models": models,
            "selection_budget_usd": requested_budget,
            "runs": [],
        }
    if not os.getenv("OPENROUTER_API_KEY", "").strip():
        return {"status": "NOT_RUN_API_KEY_MISSING", "models": models, "runs": []}
    if not confirm_dedicated_key_cap:
        return {
            "status": "NOT_RUN_5_USD_KEY_CAP_CONFIRMATION_REQUIRED",
            "note": "runner soft-stop 외에 OpenRouter 전용 테스트 key spending limit을 $5 이하로 설정했음을 확인해야 한다.",
            "runs": [],
        }
    observability_policy = policy.get("observability") if isinstance(policy.get("observability"), dict) else {}
    official_requires_langfuse = bool(observability_policy.get("official_run_requires_langfuse", False))
    if official_requires_langfuse and not allow_observability_export:
        return {
            "status": "NOT_RUN_LANGFUSE_REQUIRED",
            "note": "공식 4모델 선정은 첫 유료 호출부터 Langfuse trace를 남기도록 설정되어 있다. --allow-observability-export가 필요하다.",
            "runs": [],
        }
    if allow_observability_export and not observability_configured():
        return {
            "status": "NOT_RUN_LANGFUSE_NOT_CONFIGURED",
            "note": "Langfuse SDK/키가 준비되지 않았다. 키 값 자체는 출력하지 않는다.",
            "runs": [],
        }
    if not preflight["official_paid_run_ready"]:
        return {
            "status": "NOT_RUN_CONTRACT_APPROVAL_REQUIRED",
            "contract_approval": preflight["contract_approval"],
            "runs": [],
        }
    if allow_observability_export and not observability_auth_check():
        return {"status": "NOT_RUN_LANGFUSE_AUTH_FAILED", "runs": []}

    # 네 후보 모두 최신 ZDR filtered catalog에 있어야 inference를 시작한다.
    try:
        catalog = fetch_zdr_catalog(os.getenv("OPENROUTER_API_KEY", ""))
        price_cap = policy.get("provider_price_cap_usd_per_million") if isinstance(policy.get("provider_price_cap_usd_per_million"), dict) else {}
        max_prompt_price = float(price_cap.get("prompt", 1.0))
        max_completion_price = float(price_cap.get("completion", 5.0))
        zdr = check_zdr_eligibility(
            models,
            catalog,
            max_prompt_price_per_m=max_prompt_price,
            max_completion_price_per_m=max_completion_price,
        )
    except Exception as exc:
        return {"status": "NOT_RUN_ZDR_PREFLIGHT_ERROR", "error_type": type(exc).__name__, "runs": []}
    if zdr["status"] != "PASS":
        return {"status": "NOT_RUN_ZDR_PREFLIGHT_FAILED", "zdr": zdr, "runs": []}

    selection_run_id = uuid4().hex
    if allow_observability_export:
        ok = record_event(
            "model_selection_preflight",
            {
                "evaluation_name": "core30-model-selection-v1",
                "selection_run_id": selection_run_id,
                "dataset_sha256": preflight["dataset_sha256"],
                "quality_contract_sha256": preflight["quality_contract_sha256"],
                "status": "READY",
                "cost_usd": 0.0,
            },
        )
        if not ok:
            return {
                "status": "NOT_RUN_LANGFUSE_PREFLIGHT_WRITE_FAILED",
                "note": "유료 모델 호출 전 관측 쓰기 실패를 확인해 실행을 중단했다.",
                "runs": [],
            }

    output_dir.mkdir(parents=True, exist_ok=True)
    cumulative_cost = 0.0
    runs: list[dict[str, Any]] = []
    previous_model = os.environ.get("OPENROUTER_MODEL")
    previous_prompt_price_cap = os.environ.get("OPENROUTER_MAX_PROMPT_PRICE_PER_M")
    previous_completion_price_cap = os.environ.get("OPENROUTER_MAX_COMPLETION_PRICE_PER_M")
    os.environ["OPENROUTER_MAX_PROMPT_PRICE_PER_M"] = str(max_prompt_price)
    os.environ["OPENROUTER_MAX_COMPLETION_PRICE_PER_M"] = str(max_completion_price)
    try:
        for order, model in enumerate(models, 1):
            remaining = requested_budget - cumulative_cost
            if remaining <= 0:
                break
            os.environ["OPENROUTER_MODEL"] = model
            safe_slug = model.replace("/", "__").replace(":", "_")
            output_path = output_dir / f"{order:02d}_{safe_slug}.json"
            summary = run_model_eval(
                dataset,
                "openrouter",
                output_path,
                allow_external_llm=True,
                allow_observability_export=allow_observability_export,
                max_cost_usd=remaining,
                phase="model_selection",
                model=model,
                quality_contract_path=quality_contract_path,
                selection_run_id=selection_run_id,
                csv_output=csv_output_dir / f"{selection_run_id}_{order:02d}_{safe_slug}.csv",
            )
            pricing = ((zdr.get("pricing_by_model") or {}).get(model) if isinstance(zdr, dict) else None)
            estimate = _estimate_cost_from_catalog(summary, pricing if isinstance(pricing, dict) else None)
            model_cost = summary.get("provider_cost_usd_reported")
            run_item = {"model": model, "summary": summary, "output": str(output_path), **estimate}
            if not isinstance(model_cost, (int, float)):
                runs.append(run_item)
                return {
                    "status": "STOPPED_COST_UNKNOWN",
                    "selection_budget_usd": requested_budget,
                    "cumulative_cost_usd": round(cumulative_cost, 8),
                    "zdr": zdr,
                    "runs": runs,
                }
            cumulative_cost += float(model_cost)
            runs.append(run_item)
            if summary.get("provider_cost_complete") is not True:
                return {
                    "status": "STOPPED_COST_INCOMPLETE",
                    "selection_budget_usd": requested_budget,
                    "cumulative_cost_usd": round(cumulative_cost, 8),
                    "zdr": zdr,
                    "runs": runs,
                }
            if summary.get("observability_complete") is False:
                return {
                    "status": "STOPPED_LANGFUSE_EXPORT_FAILED",
                    "selection_run_id": selection_run_id,
                    "selection_budget_usd": requested_budget,
                    "cumulative_cost_usd": round(cumulative_cost, 8),
                    "runs": runs,
                }
            if summary.get("csv_export_complete") is not True:
                return {
                    "status": "STOPPED_CSV_EXPORT_FAILED",
                    "selection_run_id": selection_run_id,
                    "runs": runs,
                }
            if summary.get("status") not in {"COMPLETED", "COMPLETED_WITH_FAILURES"}:
                return {
                    "status": "STOPPED_MODEL_RUN_INCOMPLETE",
                    "selection_run_id": selection_run_id,
                    "selection_budget_usd": requested_budget,
                    "cumulative_cost_usd": round(cumulative_cost, 8),
                    "runs": runs,
                }
            if cumulative_cost >= requested_budget:
                break
    finally:
        if previous_model is None:
            os.environ.pop("OPENROUTER_MODEL", None)
        else:
            os.environ["OPENROUTER_MODEL"] = previous_model
        if previous_prompt_price_cap is None:
            os.environ.pop("OPENROUTER_MAX_PROMPT_PRICE_PER_M", None)
        else:
            os.environ["OPENROUTER_MAX_PROMPT_PRICE_PER_M"] = previous_prompt_price_cap
        if previous_completion_price_cap is None:
            os.environ.pop("OPENROUTER_MAX_COMPLETION_PRICE_PER_M", None)
        else:
            os.environ["OPENROUTER_MAX_COMPLETION_PRICE_PER_M"] = previous_completion_price_cap

    completed_models = sum(1 for item in runs if (item.get("summary") or {}).get("completed_rows") == int(policy.get("required_case_count", 30)))
    all_runs_complete = len(runs) == required_models and completed_models == required_models
    quality_statuses = [(item.get("summary") or {}).get("model_selection_quality_gate") for item in runs]
    status = (
        "INCOMPLETE" if not all_runs_complete
        else "COMPLETED_WITH_QUALITY_FAILURES" if "FAIL" in quality_statuses
        else "COMPLETED_AWAITING_HUMAN_REVIEW" if "REVIEW_REQUIRED" in quality_statuses
        else "COMPLETED_QUALITY_PASS" if all(value == "PASS" for value in quality_statuses)
        else "INCOMPLETE"
    )
    return {
        "status": status,
        "selection_run_id": selection_run_id,
        "selection_budget_usd": requested_budget,
        "cumulative_cost_usd": round(cumulative_cost, 8),
        "remaining_budget_usd": round(max(requested_budget - cumulative_cost, 0.0), 8),
        "models_planned": models,
        "models_run": len(runs),
        "models_completed_core30": completed_models,
        "zdr": zdr,
        "provider_price_cap_usd_per_million": {
            "prompt": max_prompt_price,
            "completion": max_completion_price,
        },
        "preflight": preflight,
        "runs": runs,
        "selection_rule": (
            "먼저 ZDR/30개 완료/Hard Fail 0/최종 계약 성공/도메인 판정 30/30을 확인하고, "
            "그 조건을 만족한 후보 사이에서 호출 수·token·비용·p50/p95 지연을 비교한다."
        ),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/dataset.jsonl")
    parser.add_argument("--policy", default="evals/model_selection_policy.json")
    parser.add_argument("--quality-contract", default="evals/core30_quality_contract.json")
    parser.add_argument("--approval", default="evals/quality_contract_approval.json")
    parser.add_argument("--candidates", default="evals/model_candidates.example.json")
    parser.add_argument("--models", default=None, help="정확한 OpenRouter model ID 4개를 쉼표로 전달")
    parser.add_argument("--budget-usd", type=float, default=None, help="4모델 전체 선택 테스트 상한. 기본/최대 $5")
    parser.add_argument("--output-dir", default="evals/results/live_runs/model_selection")
    parser.add_argument("--summary-output", default="evals/results/live_runs/model_selection_summary.json")
    parser.add_argument("--csv-output-dir", default="evals/results/model_selection_csv", help="Safe case metrics CSV directory")
    parser.add_argument("--allow-external-llm", action="store_true")
    parser.add_argument("--allow-observability-export", action="store_true")
    parser.add_argument("--confirm-dedicated-key-cap", action="store_true", help="OpenRouter 전용 key spending limit <= $5 확인")
    args = parser.parse_args()

    report = run_selection(
        dataset=Path(args.dataset),
        policy_path=Path(args.policy),
        quality_contract_path=Path(args.quality_contract),
        candidate_path=Path(args.candidates),
        output_dir=Path(args.output_dir),
        explicit_models=args.models,
        budget_usd=args.budget_usd,
        allow_external_llm=args.allow_external_llm,
        allow_observability_export=args.allow_observability_export,
        confirm_dedicated_key_cap=args.confirm_dedicated_key_cap,
        approval_path=Path(args.approval),
        csv_output_dir=Path(args.csv_output_dir),
    )
    summary_path = Path(args.summary_output)
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] not in {"COMPLETED_QUALITY_PASS", "COMPLETED_AWAITING_HUMAN_REVIEW", "COMPLETED_WITH_QUALITY_FAILURES"}:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
