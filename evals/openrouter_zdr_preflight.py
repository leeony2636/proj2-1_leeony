"""OpenRouter ZDR endpoint preflight; never sends prompts or makes billable inference calls."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
from dotenv import load_dotenv

load_dotenv(ROOT / ".env", override=False)

API_ZDR_ENDPOINTS = "https://openrouter.ai/api/v1/endpoints/zdr"


def parse_model_ids(raw: str) -> list[str]:
    models = [part.strip() for part in raw.split(",") if part.strip()]
    if not models:
        raise ValueError("MODEL_LIST_REQUIRED")
    if len(models) != len(set(models)):
        raise ValueError("DUPLICATE_MODEL_ID")
    return models


def _as_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def _per_million(per_token: float | None) -> float | None:
    return None if per_token is None else per_token * 1_000_000


def check_zdr_eligibility(
    models: list[str],
    catalog: dict[str, Any],
    *,
    max_prompt_price_per_m: float | None = None,
    max_completion_price_per_m: float | None = None,
) -> dict[str, Any]:
    """Require at least one ZDR endpoint per model, optionally under a price cap.

    `/api/v1/endpoints/zdr` already contains only ZDR endpoints. Pricing in the
    endpoint response is per token, so price caps are compared after conversion
    to USD per 1M tokens for readability.
    """
    rows = catalog.get("data")
    if not isinstance(rows, list):
        raise ValueError("INVALID_OPENROUTER_ZDR_ENDPOINT_CATALOG")

    grouped: dict[str, list[dict[str, Any]]] = {model: [] for model in models}
    for item in rows:
        if not isinstance(item, dict):
            continue
        model_id = str(item.get("model_id") or "").strip()
        if model_id in grouped:
            grouped[model_id].append(item)

    allowed: list[str] = []
    rejected: list[str] = []
    rejected_for_price: list[str] = []
    endpoint_summary: dict[str, Any] = {}
    pricing_by_model: dict[str, dict[str, Any]] = {}

    for model in models:
        candidates = grouped.get(model, [])
        under_cap: list[dict[str, Any]] = []
        normalized: list[dict[str, Any]] = []
        for row in candidates:
            pricing = row.get("pricing") if isinstance(row.get("pricing"), dict) else {}
            prompt = _as_float(pricing.get("prompt"))
            completion = _as_float(pricing.get("completion"))
            request_price = _as_float(pricing.get("request"))
            prompt_m = _per_million(prompt)
            completion_m = _per_million(completion)
            price_ok = True
            if max_prompt_price_per_m is not None:
                price_ok = price_ok and prompt_m is not None and prompt_m <= max_prompt_price_per_m
            if max_completion_price_per_m is not None:
                price_ok = price_ok and completion_m is not None and completion_m <= max_completion_price_per_m
            info = {
                "provider_name": row.get("provider_name"),
                "prompt_usd_per_million": prompt_m,
                "completion_usd_per_million": completion_m,
                "request_usd": request_price,
                "supported_parameters": row.get("supported_parameters") if isinstance(row.get("supported_parameters"), list) else [],
                "status": row.get("status"),
                "price_cap_pass": price_ok,
            }
            normalized.append(info)
            if price_ok:
                under_cap.append(row)

        if not candidates:
            rejected.append(model)
        elif not under_cap:
            rejected.append(model)
            rejected_for_price.append(model)
        else:
            allowed.append(model)
            # Conservative estimator: use the highest prompt/completion rates among
            # endpoints that still satisfy our request-level max_price cap.
            prompt_rates = []
            completion_rates = []
            request_rates = []
            for row in under_cap:
                pricing = row.get("pricing") if isinstance(row.get("pricing"), dict) else {}
                p = _as_float(pricing.get("prompt"))
                c = _as_float(pricing.get("completion"))
                r = _as_float(pricing.get("request"))
                if p is not None:
                    prompt_rates.append(p)
                if c is not None:
                    completion_rates.append(c)
                if r is not None:
                    request_rates.append(r)
            pricing_by_model[model] = {
                "prompt": max(prompt_rates) if prompt_rates else None,
                "completion": max(completion_rates) if completion_rates else None,
                "request": max(request_rates) if request_rates else None,
            }

        endpoint_summary[model] = {
            "zdr_endpoint_count": len(candidates),
            "zdr_endpoints_under_price_cap": len(under_cap),
            "endpoints": normalized,
        }

    return {
        "status": "PASS" if not rejected else "FAIL",
        "requested_models": models,
        "zdr_eligible_models": allowed,
        "rejected_or_unlisted_models": rejected,
        "rejected_for_price_cap": rejected_for_price,
        "price_cap_usd_per_million": {
            "prompt": max_prompt_price_per_m,
            "completion": max_completion_price_per_m,
        },
        "endpoint_summary": endpoint_summary,
        "pricing_by_model": pricing_by_model,
        "pricing_note": (
            "pricing_by_model은 price cap을 통과한 ZDR endpoints 중 보수적으로 가장 높은 token rate를 사용한 예상비용용 값이다. "
            "provider-reported actual cost가 최종 기준이다."
        ),
        "inference_requests": 0,
        "billable_requests": 0,
    }


def fetch_zdr_catalog(api_key: str = "", opener: Callable[..., Any] = urlopen) -> dict[str, Any]:
    token = api_key.strip()
    if not token:
        raise ValueError("OPENROUTER_API_KEY_REQUIRED_FOR_ZDR_ENDPOINT_PREVIEW")
    request = Request(
        API_ZDR_ENDPOINTS,
        headers={"Accept": "application/json", "Authorization": f"Bearer {token}"},
        method="GET",
    )
    with opener(request, timeout=20) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("data"), list):
        raise ValueError("INVALID_OPENROUTER_ZDR_ENDPOINT_CATALOG")
    return payload


def main() -> None:
    parser = argparse.ArgumentParser(description="ZDR endpoint/가격 사전검사(추론 호출/비용 없음)")
    parser.add_argument("--models", default=os.getenv("OPENROUTER_MODELS", ""), help="쉼표 구분 OpenRouter model IDs")
    parser.add_argument("--max-prompt-price", type=float, default=float(os.getenv("OPENROUTER_MAX_PROMPT_PRICE_PER_M", "1.0")))
    parser.add_argument("--max-completion-price", type=float, default=float(os.getenv("OPENROUTER_MAX_COMPLETION_PRICE_PER_M", "5.0")))
    args = parser.parse_args()
    try:
        requested = parse_model_ids(args.models)
        catalog = fetch_zdr_catalog(os.getenv("OPENROUTER_API_KEY", ""))
        report = check_zdr_eligibility(
            requested,
            catalog,
            max_prompt_price_per_m=args.max_prompt_price,
            max_completion_price_per_m=args.max_completion_price,
        )
    except Exception as exc:
        report = {
            "status": "ERROR",
            "error_type": type(exc).__name__,
            "inference_requests": 0,
            "billable_requests": 0,
        }
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
