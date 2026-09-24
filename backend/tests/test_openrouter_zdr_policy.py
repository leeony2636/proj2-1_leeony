import pytest

from evals.openrouter_zdr_preflight import check_zdr_eligibility, parse_model_ids


def _endpoint(model_id: str, prompt: str = "0.00000025", completion: str = "0.0000015", provider: str = "TestProvider"):
    return {
        "model_id": model_id,
        "provider_name": provider,
        "pricing": {"prompt": prompt, "completion": completion, "request": "0"},
        "supported_parameters": ["temperature", "max_tokens", "response_format"],
        "status": 0,
    }


def test_zdr_catalog_accepts_only_exact_listed_model_ids():
    models = ["google/gemini-3.1-flash-lite", "unknown/model"]
    catalog = {"data": [_endpoint("google/gemini-3.1-flash-lite")]}

    report = check_zdr_eligibility(models, catalog)

    assert report["status"] == "FAIL"
    assert report["zdr_eligible_models"] == ["google/gemini-3.1-flash-lite"]
    assert report["rejected_or_unlisted_models"] == ["unknown/model"]
    assert report["inference_requests"] == report["billable_requests"] == 0


def test_preview_and_qwen_are_not_special_cased_as_zdr_eligible():
    models = ["google/gemini-3-flash-preview", "qwen/qwen3.8-27b"]

    report = check_zdr_eligibility(models, {"data": []})

    assert report["status"] == "FAIL"
    assert report["zdr_eligible_models"] == []
    assert report["rejected_or_unlisted_models"] == models


def test_model_list_rejects_empty_and_duplicate_entries():
    with pytest.raises(ValueError, match="MODEL_LIST_REQUIRED"):
        parse_model_ids("  , ")
    with pytest.raises(ValueError, match="DUPLICATE_MODEL_ID"):
        parse_model_ids("vendor/model, vendor/model")


def test_zdr_endpoint_pricing_is_exposed_as_conservative_per_token_rate():
    models = ["vendor/model"]
    catalog = {
        "data": [
            _endpoint("vendor/model", prompt="0.0000004", completion="0.0000017", provider="A"),
            _endpoint("vendor/model", prompt="0.0000006", completion="0.0000022", provider="B"),
        ]
    }

    report = check_zdr_eligibility(
        models,
        catalog,
        max_prompt_price_per_m=1.0,
        max_completion_price_per_m=5.0,
    )

    assert report["status"] == "PASS"
    assert report["pricing_by_model"]["vendor/model"] == {
        "prompt": 0.0000006,
        "completion": 0.0000022,
        "request": 0.0,
    }
    assert report["endpoint_summary"]["vendor/model"]["zdr_endpoints_under_price_cap"] == 2


def test_zdr_model_is_rejected_when_all_zdr_endpoints_exceed_price_cap():
    models = ["vendor/expensive"]
    catalog = {
        "data": [
            _endpoint("vendor/expensive", prompt="0.0000015", completion="0.000006"),
        ]
    }

    report = check_zdr_eligibility(
        models,
        catalog,
        max_prompt_price_per_m=1.0,
        max_completion_price_per_m=5.0,
    )

    assert report["status"] == "FAIL"
    assert report["rejected_for_price_cap"] == ["vendor/expensive"]
