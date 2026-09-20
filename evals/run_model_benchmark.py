r"""방탈출 Agent Benchmark FINAL READY.

API 비용을 쓰기 전에 --check/--preflight-detail이 100%여야 실제 실행 가능.

핵심:
- 30문항/expected 수정 없음
- 모델은 Tool을 선택하지 않음
- Hard Guard + deterministic ToolPolicy
- 전체 SKILL.md는 서버에서 1회 로드/audit, API에는 compact policy만 사용
- 정답(expected)은 모델 호출 함수에 전달하지 않음
- 모델 99%도 REJECT
"""
from __future__ import annotations

import argparse
import ast
import inspect
import csv
import hashlib
import json
import math
import os
import re
import time
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from hard_guard import evaluate_guard
from policy_runtime import (
    cache_stats,
    discover_registered_tools_once,
    load_runtime_policy_once,
    load_skill_once,
    load_system_prompt_once,
    validate_mcp_contract,
    validate_skill_contract,
    skill_contract_diagnostics,
)
from skill_policy import (
    derive_skill_decision,
    qualifies_emotion_override,
)
from tool_policy import (
    plan_tools,
    validate_plan_against_registry,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PROJECT_ROOT / "evals"
DATASET_PATH = EVAL_DIR / "dataset.jsonl"
BLIND_DATASET_PATH = EVAL_DIR / "dataset_blind12.jsonl"
BLIND50_DATASET_PATH = EVAL_DIR / "dataset_blind50.jsonl"
BLIND50_MANIFEST_PATH = EVAL_DIR / "blind50_manifest.json"
MODEL_CONFIG_PATH = EVAL_DIR / "benchmark_models.json"
PREFLIGHT_CASES_PATH = EVAL_DIR / "preflight_cases.json"
RUNTIME_POLICY_PATH = EVAL_DIR / "runtime_policy.json"
RESULTS_DIR = EVAL_DIR / "results"

EXPECTED_CASE_COUNT = 30
BLIND_CASE_COUNT = 12
BLIND50_CASE_COUNT = 50
MIN_MODEL_COUNT = 1

TEMPERATURE = 1
MAX_TOKENS = 650
API_TIMEOUT_SECONDS = 60.0
DEFAULT_MAX_API_CALLS = 250


ALLOWED_ROUTES = {
    "HINT_DECISION",
    "INPUT_LOCATION",
    "EQUIPMENT_USAGE",
    "PROGRESS_TRANSITION",
    "MASTER_REQUEST",
    "EQUIPMENT_FAULT",
    "PROGRESS_ESTIMATION",
    "PROGRESS_VERIFICATION",
    "SPOILER_BLOCK",
    "ANSWER_EXPOSURE_BYPASS",
    "THEME_ISOLATION",
}

ALLOWED_SKILL_RULES = {
    "NONE",
    "EMOTION_OVERRIDE",
    "BASE_RULE_DEFAULT",
    "BASE_RULE_TIME_AND_PROGRESS",
    "ANSWER_REQUEST",
    "RE_REQUEST_OVERRIDE",
}

SKILL_RULE_TO_STRENGTH = {
    "EMOTION_OVERRIDE": "strong",
    "BASE_RULE_DEFAULT": "weak",
    "BASE_RULE_TIME_AND_PROGRESS": "strong",
    "ANSWER_REQUEST": "strong",
    "RE_REQUEST_OVERRIDE": "strong",
}

BOOLEAN_KEYS = (
    "needs_clarification",
    "direct_answer_request",
    "frustration_high",
)

REQUIRED_OUTPUT_KEYS = (
    "route",
    "intent",
    "emotion",
    "needs_clarification",
    "direct_answer_request",
    "frustration_high",
    "emotion_override_qualified",
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def json_dump(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def load_models() -> list[dict[str, str]]:
    value = json.loads(
        MODEL_CONFIG_PATH.read_text(encoding="utf-8")
    )
    models = value.get("models", [])

    if len(models) < MIN_MODEL_COUNT:
        raise RuntimeError(
            f"모델은 최소 {MIN_MODEL_COUNT}개 이상이어야 합니다."
        )

    names = [str(model.get("name", "")).strip() for model in models]
    if any(not name for name in names):
        raise RuntimeError("모든 모델에 name이 필요합니다.")
    if len(names) != len(set(names)):
        raise RuntimeError("benchmark_models.json의 model name은 중복될 수 없습니다.")

    for model in models:
        if not str(model.get("model", "")).strip():
            raise RuntimeError(f"model id가 없습니다: {model}")
        provider = str(model.get("provider", "openai")).lower()
        if provider != "openai":
            raise RuntimeError(
                "현재 기본 베이스는 OpenAI API 모델을 지원합니다. "
                f"지원하지 않는 provider={provider}"
            )

    return models


def load_dataset() -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in DATASET_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    if len(rows) != EXPECTED_CASE_COUNT:
        raise RuntimeError(
            f"dataset은 30건이어야 합니다. 현재={len(rows)}"
        )

    counts: dict[str, int] = defaultdict(int)

    for case in rows:
        counts[str(case["category"])] += 1

    if dict(counts) != {
        "normal": 10,
        "boundary": 12,
        "failure": 8,
    }:
        raise RuntimeError(
            f"category 계약 불일치: {dict(counts)}"
        )

    return rows


def load_blind_dataset() -> list[dict[str, Any]]:
    """최종 holdout 12문항.

    이 데이터는 기존 30문항의 복사본이 아니라
    이전 약점 영역을 새로운 표현/상태 조합으로 검증한다.
    runtime prompt/policy/code를 수정하지 않고 그대로 사용한다.
    """
    rows = [
        json.loads(line)
        for line in BLIND_DATASET_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    if len(rows) != BLIND_CASE_COUNT:
        raise RuntimeError(
            f"blind dataset은 {BLIND_CASE_COUNT}건이어야 합니다. "
            f"현재={len(rows)}"
        )

    ids = [int(case["id"]) for case in rows]

    if ids != list(range(101, 113)):
        raise RuntimeError(
            f"blind id 계약 불일치: {ids}"
        )

    required_case_keys = {
        "id",
        "category",
        "flow",
        "input",
        "expected",
        "blind_focus",
    }

    for case in rows:
        missing = required_case_keys - set(case)
        if missing:
            raise RuntimeError(
                f"blind id={case.get('id')} 필드 누락: "
                + ",".join(sorted(missing))
            )

        if case["flow"] not in ALLOWED_ROUTES:
            raise RuntimeError(
                f"blind id={case['id']} invalid flow={case['flow']}"
            )

    return rows


def load_blind50_dataset() -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in BLIND50_DATASET_PATH.read_text(
            encoding="utf-8"
        ).splitlines()
        if line.strip()
    ]

    if len(rows) != BLIND50_CASE_COUNT:
        raise RuntimeError(
            f"blind50 dataset은 {BLIND50_CASE_COUNT}건이어야 합니다. "
            f"현재={len(rows)}"
        )

    ids = [int(case["id"]) for case in rows]
    if ids != list(range(201, 251)):
        raise RuntimeError(
            f"blind50 id 계약 불일치: {ids}"
        )

    counts: dict[str, int] = defaultdict(int)
    flow_counts: dict[str, int] = defaultdict(int)

    required_case_keys = {
        "id",
        "category",
        "flow",
        "input",
        "expected",
        "blind_focus",
    }

    for case in rows:
        missing = required_case_keys - set(case)
        if missing:
            raise RuntimeError(
                f"blind50 id={case.get('id')} 필드 누락: "
                + ",".join(sorted(missing))
            )

        if case["flow"] not in ALLOWED_ROUTES:
            raise RuntimeError(
                f"blind50 id={case['id']} invalid flow={case['flow']}"
            )

        counts[str(case["category"])] += 1
        flow_counts[str(case["flow"])] += 1

    if dict(counts) != {
        "normal": 17,
        "boundary": 20,
        "failure": 13,
    }:
        raise RuntimeError(
            f"blind50 category 계약 불일치: {dict(counts)}"
        )

    expected_flows = {
        "HINT_DECISION": 25,
        "PROGRESS_TRANSITION": 3,
        "EQUIPMENT_FAULT": 3,
        "PROGRESS_ESTIMATION": 3,
        "SPOILER_BLOCK": 3,
        "ANSWER_EXPOSURE_BYPASS": 3,
        "INPUT_LOCATION": 2,
        "EQUIPMENT_USAGE": 2,
        "MASTER_REQUEST": 2,
        "PROGRESS_VERIFICATION": 2,
        "THEME_ISOLATION": 2,
    }

    if dict(flow_counts) != expected_flows:
        raise RuntimeError(
            f"blind50 flow 계약 불일치: {dict(flow_counts)}"
        )

    return rows


def load_blind50_manifest() -> dict[str, Any]:
    value = json.loads(
        BLIND50_MANIFEST_PATH.read_text(
            encoding="utf-8"
        )
    )

    if int(value.get("case_count", 0)) != BLIND50_CASE_COUNT:
        raise RuntimeError(
            "blind50 manifest case_count 불일치"
        )

    return value


def select_blind50_stage(
    dataset: list[dict[str, Any]],
    manifest: dict[str, Any],
    stage: int,
) -> list[dict[str, Any]]:
    stage_info = (
        manifest.get("stages", {})
        .get(str(stage))
    )

    if not isinstance(stage_info, dict):
        raise RuntimeError(
            f"blind50 stage {stage} 정보가 없습니다."
        )

    ids = [
        int(x)
        for x in stage_info.get("ids", [])
    ]

    by_id = {
        int(case["id"]): case
        for case in dataset
    }

    missing = [
        qid for qid in ids
        if qid not in by_id
    ]

    if missing:
        raise RuntimeError(
            f"blind50 stage {stage} missing ids={missing}"
        )

    selected = [
        by_id[qid]
        for qid in ids
    ]

    expected_cases = int(
        stage_info.get("cases", 0)
    )

    if len(selected) != expected_cases:
        raise RuntimeError(
            f"blind50 stage {stage} case count 불일치"
        )

    return selected


def verify_blind50_freeze(
    static_prompt: str,
    manifest: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    expected_dataset_hash = str(
        manifest.get("dataset_sha256", "")
    )
    actual_dataset_hash = sha256_bytes(
        BLIND50_DATASET_PATH.read_bytes()
    )

    if actual_dataset_hash != expected_dataset_hash:
        errors.append(
            "blind50 dataset sha256 mismatch"
        )

    for filename, expected_hash in (
        manifest.get("frozen_files", {})
        .items()
    ):
        path = EVAL_DIR / filename

        if not path.exists():
            errors.append(
                f"frozen file missing: {filename}"
            )
            continue

        actual_hash = sha256_bytes(
            path.read_bytes()
        )

        if actual_hash != str(expected_hash):
            errors.append(
                f"frozen file changed: {filename}"
            )

    expected_prompt_hash = str(
        manifest.get(
            "baseline_static_prompt_sha256",
            "",
        )
    )

    actual_prompt_hash = sha256_text(
        static_prompt
    )

    if (
        expected_prompt_hash
        and actual_prompt_hash
        != expected_prompt_hash
    ):
        errors.append(
            "static prompt changed after blind50 freeze"
        )

    return errors


def merge_blind50_results(
    models: list[dict[str, str]],
    dataset: list[dict[str, Any]],
    manifest: dict[str, Any],
    static_prompt: str,
    preflight: dict[str, Any],
) -> tuple[Path, Path]:
    combined_rows: list[dict[str, Any]] = []
    seen: set[tuple[str, int]] = set()

    expected_model_names = {
        str(model["name"])
        for model in models
    }

    all_stage_ids: list[int] = []

    for stage in (1, 2, 3):
        stage_info = manifest["stages"][str(stage)]
        stage_ids = [
            int(x)
            for x in stage_info["ids"]
        ]
        all_stage_ids.extend(stage_ids)

        csv_path = (
            RESULTS_DIR
            / f"blind50_stage{stage}"
            / "result.csv"
        )

        if not csv_path.exists():
            raise RuntimeError(
                f"stage {stage} 결과가 없습니다: {csv_path}"
            )

        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            rows = list(csv.DictReader(f))

        expected_rows = (
            len(stage_ids)
            * len(models)
        )

        if len(rows) != expected_rows:
            raise RuntimeError(
                f"stage {stage} row count 불일치: "
                f"{len(rows)} != {expected_rows}"
            )

        stage_seen: set[tuple[str, int]] = set()

        for row in rows:
            model_name = str(
                row.get("model_name", "")
            )
            qid = int(
                str(row.get("question_id", "0"))
            )

            if model_name not in expected_model_names:
                raise RuntimeError(
                    f"stage {stage} unknown model={model_name}"
                )

            if qid not in stage_ids:
                raise RuntimeError(
                    f"stage {stage} unexpected qid={qid}"
                )

            key = (
                model_name,
                qid,
            )

            if key in stage_seen or key in seen:
                raise RuntimeError(
                    f"duplicate result={key}"
                )

            stage_seen.add(key)
            seen.add(key)
            combined_rows.append(row)

    if sorted(all_stage_ids) != list(range(201, 251)):
        raise RuntimeError(
            "blind50 stage union이 201~250과 일치하지 않습니다."
        )

    expected_total_rows = (
        BLIND50_CASE_COUNT
        * len(models)
    )

    if len(combined_rows) != expected_total_rows:
        raise RuntimeError(
            "blind50 merged row count 불일치"
        )

    eval_dir = (
        RESULTS_DIR
        / "blind50_final"
    )
    eval_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    csv_path = eval_dir / "result.csv"
    report_path = eval_dir / "report.txt"

    with csv_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=CSV_FIELDS,
        )
        writer.writeheader()

        for row in combined_rows:
            normalized = {
                field: row.get(field, "")
                for field in CSV_FIELDS
            }
            writer.writerow(normalized)

    write_report(
        path=report_path,
        models=models,
        dataset=dataset,
        rows=combined_rows,
        static_prompt=static_prompt,
        preflight=preflight,
    )

    return csv_path, report_path


def build_model_input(
    case: dict[str, Any],
) -> dict[str, Any]:
    raw = case["input"]

    message = (
        raw.get("user_message")
        or raw.get("utterance")
        or ""
    )

    state: dict[str, Any] = {}

    if isinstance(raw.get("session_state"), dict):
        state.update(raw["session_state"])

    state_keys = (
        "remaining_time_minutes",
        "remaining_puzzle_ratio",
        "re_request",
        "last_hint_strength",
        "last_hint_same_puzzle",
        "seconds_since_last_hint",
        "puzzle_completed",
        "cause_hint",
        "progress_clarity",
        "target_puzzle_reached",
        "trigger",
        "puzzle_type",
        "claimed_progress_ratio",
        "elapsed_minutes",
        "total_puzzles_theme",
        "session_closed",
        "session_expired",
        "session_active",
        "session_status",
    )

    for key in state_keys:
        if key in raw and key not in state:
            state[key] = raw[key]

    payload: dict[str, Any] = {
        "message": message,
    }

    if state:
        payload["state"] = state

    if raw.get("conversation_history"):
        payload["history"] = raw["conversation_history"]

    if raw.get("previous_tool_results"):
        payload["tool_results"] = raw["previous_tool_results"]

    return payload


def compact_policy_text(
    policy: dict[str, Any],
) -> str:
    hints = policy["hint_rules"]

    lines = [
        "[PROJECT CORE]",
        "LLM은 자연어 의도/route/감정 신호만 구조화한다.",
        "Tool 선택과 최종 hint strength는 코드가 결정한다.",
        "",
        "[ROUTE 경계]",
    ]

    for key, value in policy.get("route_guide", {}).items():
        lines.append(f"{key}={value}")

    lines.append("")
    lines.append("[의도/경계 판정]")
    for item in policy.get("interpretation_rules", []):
        lines.append(f"- {item}")

    lines.extend([
        "",
        "[신호 정의]",
        "frustration_high=true는 강한 좌절/격한 감정 신호 자체를 뜻한다.",
        "emotion_override_qualified=true는 시간/반복시도 언급 + 무력감이 함께 있을 때만.",
        "단순 '모르겠어요' 또는 화난 말투만으로 emotion_override_qualified=true 금지.",
        "",
        "힌트 우선순위(코드 적용):",
        "ANSWER_REQUEST > RE_REQUEST_OVERRIDE > EMOTION_OVERRIDE > "
        "BASE_RULE_TIME_AND_PROGRESS > BASE_RULE_DEFAULT",
    ])

    for key in policy["hint_priority"]:
        lines.append(f"{key}={hints[key]}")

    lines.append("")
    lines.append("필수 안전규칙:")
    for item in policy["mandatory_safety"]:
        lines.append(f"- {item}")

    return "\n".join(lines)


OUTPUT_CONTRACT = """
[OUTPUT]
JSON 하나만 출력. 설명문 금지.

route:
HINT_DECISION | INPUT_LOCATION | EQUIPMENT_USAGE | PROGRESS_TRANSITION |
MASTER_REQUEST | EQUIPMENT_FAULT | PROGRESS_ESTIMATION |
PROGRESS_VERIFICATION | SPOILER_BLOCK | ANSWER_EXPOSURE_BYPASS |
THEME_ISOLATION

규칙:
- Tool 이름을 출력하지 않는다.
- Skill rule 또는 weak/strong을 출력하지 않는다.
- intent/emotion은 실제 SYSTEM_PROMPT의 native 값을 그대로 출력한다.
- needs_clarification은 추가 사용자 확인이 필요한 경우만 true.
- direct_answer_request는 정답/번호 직접 요구 신호.
- frustration_high는 강한 좌절/격한 감정 신호 자체만 표시한다.
- emotion_override_qualified는 시간/반복시도 + 무력감 복합조건일 때만 true.
- 정답, reason, context echo는 출력하지 않는다.

정확히 7개 키:
{"route":"","intent":"","emotion":"","needs_clarification":false,"direct_answer_request":false,"frustration_high":false,"emotion_override_qualified":false}
""".strip()


def build_static_prompt() -> str:
    # 프로세스당 1회 로드된 공통 소스로 동일 prefix를 만든다.
    return (
        load_system_prompt_once().strip()
        + "\n\n"
        + compact_policy_text(
            load_runtime_policy_once()
        )
        + "\n\n"
        + OUTPUT_CONTRACT
    )


def validate_output(
    parsed: dict[str, Any],
) -> tuple[bool, list[str]]:
    errors: list[str] = []

    missing = [
        key
        for key in REQUIRED_OUTPUT_KEYS
        if key not in parsed
    ]

    if missing:
        errors.append(
            "missing=" + ",".join(missing)
        )

    extra = set(parsed) - set(REQUIRED_OUTPUT_KEYS)

    if extra:
        errors.append(
            "extra=" + ",".join(sorted(extra))
        )


    if parsed.get("route") not in ALLOWED_ROUTES:
        errors.append("invalid_route")

    if not isinstance(parsed.get("intent"), str) or not parsed["intent"].strip():
        errors.append("invalid_intent")

    if not isinstance(parsed.get("emotion"), str) or not parsed["emotion"].strip():
        errors.append("invalid_emotion")

    for key in BOOLEAN_KEYS:
        if not isinstance(parsed.get(key), bool):
            errors.append(f"{key}_must_be_bool")

    if not isinstance(
        parsed.get("emotion_override_qualified"),
        bool,
    ):
        errors.append(
            "emotion_override_qualified_must_be_bool"
        )

    return len(errors) == 0, errors


def extract_json(
    text: str,
) -> dict[str, Any]:
    stripped = text.strip()

    if stripped.startswith("```"):
        lines = stripped.splitlines()

        if lines and lines[0].startswith("```"):
            lines = lines[1:]

        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]

        stripped = "\n".join(lines).strip()

    try:
        value = json.loads(stripped)

        if isinstance(value, dict):
            return value
    except json.JSONDecodeError:
        pass

    start = stripped.find("{")
    end = stripped.rfind("}")

    if start < 0 or end <= start:
        raise ValueError(
            "JSON 객체를 찾지 못했습니다."
        )

    value = json.loads(
        stripped[start:end + 1]
    )

    if not isinstance(value, dict):
        raise ValueError(
            "JSON 최상위가 객체가 아닙니다."
        )

    return value


def expected_skill_rule(
    case: dict[str, Any],
) -> str:
    value = case["expected"].get("reason_code")

    if value is None:
        return "NONE"

    value = str(value).strip().upper()

    if value in ALLOWED_SKILL_RULES:
        return value

    return "NONE"


def make_client() -> OpenAI:
    api_key = os.getenv(
        "OPENAI_API_KEY",
        "",
    ).strip()

    if not api_key:
        raise RuntimeError(
            ".env에 OPENAI_API_KEY가 없습니다."
        )

    return OpenAI(
        api_key=api_key,
        max_retries=0,
    )


def usage_value(
    usage: Any,
    name: str,
) -> int | str:
    if usage is None:
        return ""

    value = getattr(
        usage,
        name,
        None,
    )

    if value is None:
        return ""

    try:
        return int(value)
    except Exception:
        return value


def reasoning_tokens(
    usage: Any,
) -> int | str:
    if usage is None:
        return ""

    details = getattr(
        usage,
        "completion_tokens_details",
        None,
    )

    if details is None:
        return ""

    value = getattr(
        details,
        "reasoning_tokens",
        None,
    )

    if value is None:
        return ""

    try:
        return int(value)
    except Exception:
        return value


def cached_prompt_tokens(
    usage: Any,
) -> int | str:
    if usage is None:
        return ""

    details = getattr(
        usage,
        "prompt_tokens_details",
        None,
    )

    if details is None:
        return ""

    value = getattr(
        details,
        "cached_tokens",
        None,
    )

    if value is None:
        return ""

    try:
        return int(value)
    except Exception:
        return value


def call_model(
    client: OpenAI,
    model_config: dict[str, Any],
    static_prompt: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """중요: expected/case/category/question id를 받지 않는다."""
    started = time.perf_counter()

    model_id = str(model_config["model"])
    max_tokens = int(model_config.get("max_completion_tokens", MAX_TOKENS))
    timeout_seconds = float(model_config.get("timeout_seconds", API_TIMEOUT_SECONDS))

    request_kwargs: dict[str, Any] = {
        "model": model_id,
        "messages": [
            {"role": "system", "content": static_prompt},
            {"role": "user", "content": json_dump(payload)},
        ],
        "max_completion_tokens": max_tokens,
        "timeout": timeout_seconds,
    }
    if bool(model_config.get("send_temperature", True)):
        request_kwargs["temperature"] = model_config.get("temperature", TEMPERATURE)

    response = client.chat.completions.create(**request_kwargs)

    latency_ms = round(
        (time.perf_counter() - started) * 1000,
        2,
    )

    choice = response.choices[0]
    content = choice.message.content or ""
    finish_reason = (
        getattr(choice, "finish_reason", "")
        or ""
    )
    usage = getattr(response, "usage", None)

    p_tokens = usage_value(
        usage,
        "prompt_tokens",
    )
    c_tokens = usage_value(
        usage,
        "completion_tokens",
    )
    t_tokens = usage_value(
        usage,
        "total_tokens",
    )
    r_tokens = reasoning_tokens(usage)
    cached = cached_prompt_tokens(usage)

    uncached: int | str = ""

    if isinstance(p_tokens, int):
        if isinstance(cached, int):
            uncached = max(
                p_tokens - cached,
                0,
            )
        else:
            uncached = p_tokens

    visible: int | str = ""

    if isinstance(c_tokens, int):
        if isinstance(r_tokens, int):
            visible = max(
                c_tokens - r_tokens,
                0,
            )
        else:
            visible = c_tokens

    result: dict[str, Any] = {
        "status": "OK",
        "finish_reason": finish_reason,
        "json_valid": False,
        "schema_valid": False,
        "schema_errors": "",
        "latency_ms": latency_ms,
        "prompt_tokens": p_tokens,
        "cached_prompt_tokens": cached,
        "uncached_prompt_tokens": uncached,
        "completion_tokens": c_tokens,
        "reasoning_tokens": r_tokens,
        "visible_completion_tokens": visible,
        "total_tokens": t_tokens,
        "completion_usage_ratio": (
            round(c_tokens / max_tokens, 4)
            if isinstance(c_tokens, int)
            else ""
        ),
        "completion_limit_hit": int(
            str(finish_reason).lower() == "length"
            or (
                isinstance(c_tokens, int)
                and c_tokens >= max_tokens
            )
        ),
        "raw_response": content,
        "parsed_json": "",
        "error_type": "",
        "error_message": "",
    }

    try:
        parsed = extract_json(content)
    except Exception as exc:
        result["status"] = "JSON_ERROR"
        result["error_type"] = type(exc).__name__
        result["error_message"] = str(exc)[:1000]
        return result

    result["json_valid"] = True
    result["parsed_json"] = json_dump(parsed)

    schema_valid, errors = validate_output(parsed)

    result["schema_valid"] = schema_valid
    result["schema_errors"] = json_dump(errors)

    if not schema_valid:
        result["status"] = "CONTRACT_ERROR"

    for key in REQUIRED_OUTPUT_KEYS:
        result[key] = parsed.get(key, "")

    return result


def score_case(
    case: dict[str, Any],
    payload: dict[str, Any],
    model_result: dict[str, Any],
    actual_tools: set[str],
) -> dict[str, Any]:
    expected = case["expected"]

    route_match = int(
        model_result.get("route") == case["flow"]
    )

    signal_checked = 0
    signal_correct = 0
    for key in BOOLEAN_KEYS:
        if key not in expected:
            continue
        signal_checked += 1
        signal_correct += int(
            model_result.get(key) == expected.get(key)
        )
    signal_pass = int(signal_checked == signal_correct)

    expected_emotion_override = (
        qualifies_emotion_override(payload)
    )
    emotion_override_match = int(
        model_result.get("emotion_override_qualified")
        == expected_emotion_override
    )

    schema_valid = (
        str(model_result.get("schema_valid")) == "True"
        or model_result.get("schema_valid") is True
    )

    # 모델 자체 평가는 자연어/route/신호 파악만 본다.
    model_case_pass = int(
        schema_valid
        and route_match == 1
        and signal_pass == 1
        and emotion_override_match == 1
    )

    # 서비스 보호 route
    guard = evaluate_guard(payload)
    effective_route = (
        guard.forced_route
        if guard.matched and guard.forced_route is not None
        else str(model_result.get("route", ""))
    )
    effective_route_match = int(
        effective_route == case["flow"]
    )

    # 최종 Skill은 모델이 아니라 deterministic code가 결정
    skill = derive_skill_decision(
        effective_route,
        payload,
        model_result,
    )
    expected_rule = expected_skill_rule(case)
    expected_strength = expected.get("hint_strength")

    skill_rule_match = int(
        skill.rule == expected_rule
    )
    strength_checked = (
        expected_rule != "NONE"
        and expected_strength in {"weak", "strong"}
    )
    strength_match = (
        int(skill.strength == expected_strength)
        if strength_checked
        else 1
    )
    skill_policy_pass = int(
        skill_rule_match == 1
        and strength_match == 1
    )

    if guard.matched and guard.action == "CLOSED":
        policy_tools: tuple[str, ...] = ()
        policy_reason = guard.reason
        registry_ok = True
        registry_missing: list[str] = []
    else:
        plan = plan_tools(
            effective_route,
            payload,
        )
        policy_tools = plan.tools
        policy_reason = plan.reason
        registry_ok, registry_missing = (
            validate_plan_against_registry(
                plan,
                actual_tools,
            )
        )

    expected_tools = tuple(
        expected.get("recommended_tools", [])
    )
    tool_policy_pass = int(
        registry_ok
        and policy_tools == expected_tools
    )

    # 실제 서비스 게이트는 Guard 보정 route + SkillPolicy + ToolPolicy로 판단.
    service_case_pass = int(
        schema_valid
        and effective_route_match == 1
        and skill_policy_pass == 1
        and tool_policy_pass == 1
    )

    return {
        "route_match": route_match,
        "expected_skill_rule": expected_rule,
        "derived_skill_rule": skill.rule,
        "skill_rule_match": skill_rule_match,
        "skill_policy_reason": skill.reason,
        "derived_hint_strength": skill.strength or "",
        "expected_hint_strength": expected_strength or "",
        "skill_strength_checked": int(strength_checked),
        "skill_strength_match": strength_match,
        "skill_policy_pass": skill_policy_pass,
        "signal_checked": signal_checked,
        "signal_correct": signal_correct,
        "signal_pass": signal_pass,
        "emotion_override_match": emotion_override_match,
        "model_case_pass": model_case_pass,
        "guard_matched": int(guard.matched),
        "guard_action": guard.action,
        "guard_forced_route": guard.forced_route or "",
        "guard_skip_llm_service": int(
            guard.skip_llm_in_service
        ),
        "effective_route": effective_route,
        "effective_route_match": effective_route_match,
        "policy_tools": json_dump(list(policy_tools)),
        "policy_tool_reason": policy_reason,
        "expected_tools": json_dump(list(expected_tools)),
        "tool_registry_ok": int(registry_ok),
        "tool_registry_missing": json_dump(registry_missing),
        "tool_policy_pass": tool_policy_pass,
        "service_case_pass": service_case_pass,
    }


def source_leak_audit() -> list[str]:
    """runtime 정책 코드가 정답표를 참조하지 않는지 AST로 검사."""
    errors: list[str] = []

    for filename, function_name in (
        ("skill_policy.py", "derive_skill_decision"),
        ("tool_policy.py", "plan_tools"),
        ("hard_guard.py", "evaluate_guard"),
    ):
        source = (EVAL_DIR / filename).read_text(encoding="utf-8")
        tree = ast.parse(source)

        forbidden_names = {
            "expected",
            "question_id",
            "category",
            "dataset",
        }

        used_names = {
            node.id
            for node in ast.walk(tree)
            if isinstance(node, ast.Name)
        }

        leaked = sorted(
            forbidden_names & used_names
        )
        if leaked:
            errors.append(
                f"{filename}:forbidden_names={leaked}"
            )

        target = None
        for node in tree.body:
            if (
                isinstance(node, ast.FunctionDef)
                and node.name == function_name
            ):
                target = node
                break

        if target is None:
            errors.append(
                f"{filename}:{function_name}_missing"
            )

    # 모델 API 함수 자체도 case/expected/category/question_id를 입력받지 않아야 함.
    params = set(
        inspect.signature(call_model).parameters
    )
    forbidden_params = {
        "case",
        "expected",
        "category",
        "question_id",
    }
    bad_params = sorted(
        params & forbidden_params
    )
    if bad_params:
        errors.append(
            f"call_model:forbidden_params={bad_params}"
        )

    # build_static_prompt가 full SKILL.md를 직접 읽거나 붙이지 않는지 소스 검사.
    source = inspect.getsource(
        build_static_prompt
    )
    if "load_skill_once" in source:
        errors.append(
            "build_static_prompt:full_skill_reference"
        )

    return errors


def scoring_contract_self_test(
    dataset: list[dict[str, Any]],
    actual_tools: set[str],
) -> tuple[int, list[dict[str, Any]]]:
    """채점기 자체가 원본 30문항 계약과 모순되지 않는지 API 없이 확인.

    mock output은 expected를 이용해 만드는 '테스트 하네스 내부 self-test'이며
    call_model/ToolPolicy/HardGuard에는 전달되지 않는다.
    """
    passed = 0
    details: list[dict[str, Any]] = []

    for case in dataset:
        expected = case["expected"]
        expected_rule = expected_skill_rule(case)
        payload = build_model_input(case)

        mock: dict[str, Any] = {
            "status": "OK",
            "schema_valid": True,
            "route": case["flow"],
            "intent": "MOCK_NATIVE_INTENT",
            "emotion": "MOCK_NATIVE_EMOTION",
            "needs_clarification": expected.get(
                "needs_clarification",
                False,
            ),
            "direct_answer_request": expected.get(
                "direct_answer_request",
                False,
            ),
            "frustration_high": expected.get(
                "frustration_high",
                False,
            ),
            "emotion_override_qualified": (
                qualifies_emotion_override(payload)
            ),
        }

        score = score_case(
            case=case,
            payload=payload,
            model_result=mock,
            actual_tools=actual_tools,
        )

        ok = (
            score["model_case_pass"] == 1
            and score["skill_policy_pass"] == 1
            and score["tool_policy_pass"] == 1
            and score["service_case_pass"] == 1
        )
        passed += int(ok)

        if not ok:
            details.append({
                "id": case["id"],
                "flow": case["flow"],
                "expected_rule": expected_rule,
                "expected_strength": expected.get(
                    "hint_strength"
                ),
                "score": score,
            })

    return passed, details


def load_preflight_cases() -> dict[str, Any]:
    return json.loads(
        PREFLIGHT_CASES_PATH.read_text(
            encoding="utf-8"
        )
    )


def run_preflight(
    dataset: list[dict[str, Any]],
) -> dict[str, Any]:
    policy = load_runtime_policy_once()
    skill = load_skill_once()
    actual_tools = set(
        discover_registered_tools_once()
    )
    preflight = load_preflight_cases()

    scoring_passed, scoring_failures = (
        scoring_contract_self_test(
            dataset,
            actual_tools,
        )
    )

    result: dict[str, Any] = {
        "skill_contract_errors": validate_skill_contract(
            skill,
            policy,
        ),
        "skill_contract_diagnostics": skill_contract_diagnostics(
            skill,
            policy,
        ),
        "mcp_missing_required": validate_mcp_contract(
            actual_tools,
        ),
        "source_leak_errors": source_leak_audit(),
        "scoring_contract_passed": scoring_passed,
        "scoring_contract_failures": scoring_failures,
        "skill_synthetic": [],
        "tool_synthetic": [],
        "guard_synthetic": [],
        "dataset_tool_contract": [],
    }

    # 공통 데이터가 실제로 cache되는지 확인하기 위해 반복 접근
    load_system_prompt_once()
    load_system_prompt_once()
    load_skill_once()
    load_skill_once()
    load_runtime_policy_once()
    load_runtime_policy_once()
    discover_registered_tools_once()
    discover_registered_tools_once()

    for case in preflight.get("skill_policy", []):
        decision = derive_skill_decision(
            route=case["route"],
            signals=case["signals"],
            payload=case["payload"],
        )

        passed = (
            decision.rule == case["rule"]
            and decision.strength
            == case["strength"]
        )

        result["skill_synthetic"].append({
            "name": case["name"],
            "pass": int(passed),
            "rule": decision.rule,
            "strength": decision.strength,
            "expected_rule": case["rule"],
            "expected_strength": case["strength"],
        })

    for case in preflight["tool_policy"]:
        plan = plan_tools(
            case["route"],
            case["payload"],
        )
        expected = tuple(case["tools"])
        registry_ok, registry_missing = (
            validate_plan_against_registry(
                plan,
                actual_tools,
            )
        )
        passed = (
            registry_ok
            and plan.tools == expected
        )

        result["tool_synthetic"].append({
            "name": case["name"],
            "pass": int(passed),
            "planned": list(plan.tools),
            "expected": list(expected),
            "registry_missing": registry_missing,
        })

    for case in preflight["hard_guard"]:
        decision = evaluate_guard(
            case["payload"]
        )
        passed = (
            decision.matched == case["matched"]
            and decision.forced_route == case["route"]
            and decision.action == case["action"]
        )

        result["guard_synthetic"].append({
            "name": case["name"],
            "pass": int(passed),
            "matched": decision.matched,
            "route": decision.forced_route,
            "action": decision.action,
        })

    # 30문항 전체 Tool 계약 회귀 검사.
    # 이 단계는 model test가 아니라 ToolPolicyEngine unit/regression test.
    for case in dataset:
        payload = build_model_input(case)
        guard = evaluate_guard(payload)

        route = (
            guard.forced_route
            if guard.matched
            and guard.forced_route is not None
            else str(case["flow"])
        )

        if guard.matched and guard.action == "CLOSED":
            planned = ()
            registry_ok = True
        else:
            plan = plan_tools(
                route,
                payload,
            )
            planned = plan.tools
            registry_ok, _ = (
                validate_plan_against_registry(
                    plan,
                    actual_tools,
                )
            )

        expected = tuple(
            case["expected"].get(
                "recommended_tools",
                [],
            )
        )

        passed = (
            registry_ok
            and planned == expected
        )

        result["dataset_tool_contract"].append({
            "id": case["id"],
            "pass": int(passed),
            "planned": list(planned),
            "expected": list(expected),
        })

    result["cache_stats"] = cache_stats()

    skill_syn_pass = sum(
        x["pass"]
        for x in result["skill_synthetic"]
    )
    tool_syn_pass = sum(
        x["pass"]
        for x in result["tool_synthetic"]
    )
    guard_syn_pass = sum(
        x["pass"]
        for x in result["guard_synthetic"]
    )
    dataset_tool_pass = sum(
        x["pass"]
        for x in result["dataset_tool_contract"]
    )

    cache_ok = all(
        stats["misses"] == 1
        and stats["hits"] >= 1
        for stats in result["cache_stats"].values()
    )

    result["summary"] = {
        "skill_contract": int(
            len(result["skill_contract_errors"]) == 0
        ),
        "mcp_contract": int(
            len(result["mcp_missing_required"]) == 0
        ),
        "skill_synthetic": (
            f"{skill_syn_pass}/"
            f"{len(result['skill_synthetic'])}"
        ),
        "tool_synthetic": (
            f"{tool_syn_pass}/"
            f"{len(result['tool_synthetic'])}"
        ),
        "guard_synthetic": (
            f"{guard_syn_pass}/"
            f"{len(result['guard_synthetic'])}"
        ),
        "dataset_tool_contract": (
            f"{dataset_tool_pass}/"
            f"{len(result['dataset_tool_contract'])}"
        ),
        "cache_once": int(cache_ok),
        "source_leak_audit": int(
            len(result["source_leak_errors"]) == 0
        ),
        "scoring_contract": (
            f"{scoring_passed}/{len(dataset)}"
        ),
    }

    result["all_pass"] = (
        len(result["skill_contract_errors"]) == 0
        and len(result["mcp_missing_required"]) == 0
        and len(result["source_leak_errors"]) == 0
        and scoring_passed == len(dataset)
        and skill_syn_pass == len(result["skill_synthetic"])
        and tool_syn_pass == len(result["tool_synthetic"])
        and guard_syn_pass == len(result["guard_synthetic"])
        and dataset_tool_pass == len(result["dataset_tool_contract"])
        and cache_ok
    )

    return result


def print_preflight(
    result: dict[str, Any],
    detail: bool,
) -> None:
    s = result["summary"]

    print("[FINAL READY PREFLIGHT - API 호출 없음]")
    print("Skill contract:", "PASS" if s["skill_contract"] else "FAIL")
    print("MCP contract:", "PASS" if s["mcp_contract"] else "FAIL")
    print("Synthetic SkillPolicy:", s["skill_synthetic"])
    print("Synthetic ToolPolicy:", s["tool_synthetic"])
    print("Synthetic HardGuard:", s["guard_synthetic"])
    print("30-case Tool contract:", s["dataset_tool_contract"])
    print("30-case Scoring contract:", s["scoring_contract"])
    print(
        "No-answer-leak audit:",
        "PASS" if s["source_leak_audit"] else "FAIL",
    )
    print("Source cache once:", "PASS" if s["cache_once"] else "FAIL")
    print()

    if result["skill_contract_errors"]:
        print("Skill contract errors:")
        for x in result["skill_contract_errors"]:
            print(" -", x)

    if result["mcp_missing_required"]:
        print("Missing MCP tools:")
        for x in result["mcp_missing_required"]:
            print(" -", x)

    if detail:
        print("\n[Skill synthetic]")
        for x in result["skill_synthetic"]:
            print(x)

        print("\n[Tool synthetic]")
        for x in result["tool_synthetic"]:
            print(x)

        print("\n[HardGuard synthetic]")
        for x in result["guard_synthetic"]:
            print(x)

        print("\n[30-case Tool contract failures only]")
        for x in result["dataset_tool_contract"]:
            if not x["pass"]:
                print(x)

        print("\n[Source leak audit]")
        print(
            json.dumps(
                result["source_leak_errors"],
                ensure_ascii=False,
                indent=2,
            )
        )

        print("\n[Scoring contract failures]")
        print(
            json.dumps(
                result["scoring_contract_failures"],
                ensure_ascii=False,
                indent=2,
            )
        )

        print("\n[Skill contract diagnostics]")
        print(
            json.dumps(
                result["skill_contract_diagnostics"],
                ensure_ascii=False,
                indent=2,
            )
        )

        print("\n[Cache stats]")
        print(
            json.dumps(
                result["cache_stats"],
                ensure_ascii=False,
                indent=2,
            )
        )

    print()
    print(
        "PREFLIGHT GATE:",
        "PASS" if result["all_pass"] else "FAIL",
    )


def select_dataset(
    dataset: list[dict[str, Any]],
    ids_arg: str | None,
    limit: int | None,
) -> list[dict[str, Any]]:
    if ids_arg:
        ids = [
            int(x.strip())
            for x in ids_arg.split(",")
            if x.strip()
        ]

        if len(ids) != len(set(ids)):
            raise RuntimeError(
                "--ids에 중복 ID가 있습니다."
            )

        by_id = {
            int(case["id"]): case
            for case in dataset
        }

        missing = [
            x
            for x in ids
            if x not in by_id
        ]

        if missing:
            raise RuntimeError(
                f"dataset에 없는 ID: {missing}"
            )

        return [
            by_id[x]
            for x in ids
        ]

    if limit is not None:
        if not 1 <= limit <= 30:
            raise RuntimeError("--limit은 1~30")
        return dataset[:limit]

    return dataset


def safe_eval_name(value: str) -> str:
    cleaned = re.sub(
        r"[^0-9A-Za-z가-힣._-]+",
        "_",
        value.strip(),
    ).strip("._-")

    return cleaned or "evaluation"


def build_eval_name(
    dataset: list[dict[str, Any]],
    args: argparse.Namespace,
) -> str:
    if args.eval_name:
        return safe_eval_name(args.eval_name)

    ids = [
        str(case["id"])
        for case in dataset
    ]

    if len(dataset) == 30:
        return "eval_30_all"

    return (
        f"eval_{len(dataset):02d}_ids_"
        + "-".join(ids)
    )


CSV_FIELDS = [
    'run_id',
    'model_name',
    'model_id',
    'question_id',
    'category',
    'flow',
    'status',
    'finish_reason',
    'json_valid',
    'schema_valid',
    'schema_errors',
    'route',
    'route_match',
    'intent',
    'emotion',
    'needs_clarification',
    'direct_answer_request',
    'frustration_high',
    'emotion_override_qualified',
    'emotion_override_match',
    'signal_checked',
    'signal_correct',
    'signal_pass',
    'model_case_pass',
    'expected_skill_rule',
    'derived_skill_rule',
    'skill_rule_match',
    'skill_policy_reason',
    'skill_policy_pass',
    'derived_hint_strength',
    'expected_hint_strength',
    'skill_strength_checked',
    'skill_strength_match',
    'guard_matched',
    'guard_action',
    'guard_forced_route',
    'guard_skip_llm_service',
    'effective_route',
    'effective_route_match',
    'policy_tools',
    'policy_tool_reason',
    'expected_tools',
    'tool_registry_ok',
    'tool_registry_missing',
    'tool_policy_pass',
    'service_case_pass',
    'prompt_tokens',
    'cached_prompt_tokens',
    'uncached_prompt_tokens',
    'completion_tokens',
    'reasoning_tokens',
    'visible_completion_tokens',
    'total_tokens',
    'completion_usage_ratio',
    'completion_limit_hit',
    'latency_ms',
    'raw_response',
    'parsed_json',
    'error_type',
    'error_message',
]


def numeric_sum(
    rows: list[dict[str, Any]],
    key: str,
) -> int:
    total = 0

    for row in rows:
        value = row.get(key, "")

        try:
            if value != "":
                total += int(value)
        except Exception:
            pass

    return total


def numeric_float_values(
    rows: list[dict[str, Any]],
    key: str,
) -> list[float]:
    values: list[float] = []

    for row in rows:
        raw = row.get(key, "")

        if raw in ("", None):
            continue

        try:
            values.append(float(raw))
        except Exception:
            pass

    return values


def percentile_nearest_rank(
    values: list[float],
    percentile: float,
) -> float:
    if not values:
        return 0.0

    ordered = sorted(values)
    rank = max(
        1,
        math.ceil(percentile * len(ordered)),
    )
    return ordered[rank - 1]


def lower_model_label(
    metrics: dict[str, float],
) -> str:
    if not metrics:
        return "N/A"

    best = min(metrics.values())
    names = [
        name
        for name, value in metrics.items()
        if value == best
    ]

    if len(names) == len(metrics):
        return "TIE"

    return ", ".join(names)


def write_report(
    path: Path,
    models: list[dict[str, str]],
    dataset: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    static_prompt: str,
    preflight: dict[str, Any],
) -> None:
    by_model: dict[
        str,
        list[dict[str, Any]],
    ] = defaultdict(list)

    for row in rows:
        by_model[
            str(row["model_name"])
        ].append(row)

    lines = [
        "방탈출 Agent Benchmark FINAL READY",
        "=" * 72,
        "",
        "[Preflight]",
        f"- gate: {'PASS' if preflight['all_pass'] else 'FAIL'}",
        f"- synthetic SkillPolicy: {preflight['summary']['skill_synthetic']}",
        f"- synthetic ToolPolicy: {preflight['summary']['tool_synthetic']}",
        f"- synthetic HardGuard: {preflight['summary']['guard_synthetic']}",
        f"- 30-case Tool contract: {preflight['summary']['dataset_tool_contract']}",
        f"- 30-case Scoring contract: {preflight['summary']['scoring_contract']}",
        f"- no-answer-leak audit: {preflight['summary']['source_leak_audit']}",
        f"- source cache once: {preflight['summary']['cache_once']}",
        "",
        "[Frozen test identity]",
        f"- dataset cases: {len(dataset)}",
        f"- dataset sha256: {sha256_text(chr(10).join(json_dump(case) for case in dataset))}",
        f"- static prompt sha256: {sha256_text(static_prompt)}",
        f"- runtime policy sha256: {sha256_bytes(RUNTIME_POLICY_PATH.read_bytes())}",
        "",
        "[Prompt]",
        f"- static prompt chars: {len(static_prompt)}",
        "- full SKILL.md is not sent each call",
        "- fixed prefix kept identical for provider prompt cache",
        "",
        "[Gate]",
        "- any model error => model REJECT",
        "- service_case_pass must be 100%",
        "",
    ]

    for model in models:
        name = str(model["name"])
        mr = by_model.get(name, [])
        calls = len(mr)

        model_pass = numeric_sum(
            mr,
            "model_case_pass",
        )
        skill_pass = numeric_sum(
            mr,
            "skill_policy_pass",
        )
        tool_pass = numeric_sum(
            mr,
            "tool_policy_pass",
        )
        service_pass = numeric_sum(
            mr,
            "service_case_pass",
        )
        route = numeric_sum(
            mr,
            "route_match",
        )

        prompt_total = numeric_sum(
            mr,
            "prompt_tokens",
        )
        cached_total = numeric_sum(
            mr,
            "cached_prompt_tokens",
        )
        uncached_total = numeric_sum(
            mr,
            "uncached_prompt_tokens",
        )
        completion_total = numeric_sum(
            mr,
            "completion_tokens",
        )
        reasoning_total = numeric_sum(
            mr,
            "reasoning_tokens",
        )
        total_total = numeric_sum(
            mr,
            "total_tokens",
        )
        limit_hits = numeric_sum(
            mr,
            "completion_limit_hit",
        )
        latencies = numeric_float_values(
            mr,
            "latency_ms",
        )
        total_latency = sum(latencies)
        avg_latency = (
            total_latency / len(latencies)
            if latencies
            else 0.0
        )
        median_latency = (
            sorted(latencies)[len(latencies) // 2]
            if len(latencies) % 2 == 1
            else (
                (
                    sorted(latencies)[len(latencies) // 2 - 1]
                    + sorted(latencies)[len(latencies) // 2]
                ) / 2
                if latencies
                else 0.0
            )
        )
        p95_latency = percentile_nearest_rank(
            latencies,
            0.95,
        )

        model_accepted = (
            calls > 0
            and model_pass == calls
        )
        service_accepted = (
            calls > 0
            and service_pass == calls
        )

        # Category breakdown is analysis only.
        # It never changes expected values or scoring.
        category_rows: list[str] = []
        for category_name in (
            "normal",
            "boundary",
            "failure",
        ):
            cr = [
                row
                for row in mr
                if row.get("category") == category_name
            ]
            if not cr:
                continue

            cr_calls = len(cr)
            cr_model = numeric_sum(
                cr,
                "model_case_pass",
            )
            cr_service = numeric_sum(
                cr,
                "service_case_pass",
            )

            category_rows.append(
                f"  {category_name}: "
                f"model={cr_model}/{cr_calls}, "
                f"service={cr_service}/{cr_calls}"
            )

        failed_model_ids = [
            str(row.get("question_id"))
            for row in mr
            if str(row.get("model_case_pass"))
            not in ("1", "True", "true")
        ]
        failed_service_ids = [
            str(row.get("question_id"))
            for row in mr
            if str(row.get("service_case_pass"))
            not in ("1", "True", "true")
        ]

        lines.extend([
            f"[{name}] {model['model']}",
            f"- route: {route}/{calls}",
            f"- model_case_pass: {model_pass}/{calls}",
            f"- deterministic_skill_pass: {skill_pass}/{calls}",
            f"- deterministic_tool_pass: {tool_pass}/{calls}",
            f"- service_case_pass: {service_pass}/{calls}",
            f"- MODEL GATE: {'ACCEPT' if model_accepted else 'REJECT'}",
            f"- SERVICE GATE: {'ACCEPT' if service_accepted else 'REJECT'}",
            "- category breakdown:",
            *category_rows,
            (
                "- model failed ids: "
                + (
                    ", ".join(failed_model_ids)
                    if failed_model_ids
                    else "none"
                )
            ),
            (
                "- service failed ids: "
                + (
                    ", ".join(failed_service_ids)
                    if failed_service_ids
                    else "none"
                )
            ),
            f"- prompt total: {prompt_total}",
            f"- cached prompt total: {cached_total}",
            f"- uncached prompt total: {uncached_total}",
            f"- completion total: {completion_total}",
            f"- reasoning total: {reasoning_total}",
            f"- total tokens: {total_total}",
            f"- completion limit hit: {limit_hits}/{calls}",
            f"- total latency ms: {total_latency:.2f}",
            f"- avg latency ms: {avg_latency:.2f}",
            f"- median latency ms: {median_latency:.2f}",
            f"- p95 latency ms: {p95_latency:.2f}",
        ])

        if calls:
            lines.extend([
                f"- avg prompt/call: {prompt_total / calls:.2f}",
                f"- avg uncached prompt/call: {uncached_total / calls:.2f}",
                f"- avg total/call: {total_total / calls:.2f}",
            ])

        lines.append("- cases:")

        for row in mr:
            lines.append(
                "  "
                f"id={row.get('question_id')} "
                f"model={row.get('model_case_pass')} "
                f"skill={row.get('skill_policy_pass')} "
                f"guard={row.get('guard_action')} "
                f"tool={row.get('tool_policy_pass')} "
                f"service={row.get('service_case_pass')} "
                f"prompt={row.get('prompt_tokens')} "
                f"cached={row.get('cached_prompt_tokens')} "
                f"uncached={row.get('uncached_prompt_tokens')} "
                f"completion={row.get('completion_tokens')} "
                f"reasoning={row.get('reasoning_tokens')} "
                f"total={row.get('total_tokens')}"
            )

        lines.append("")

    # --------------------------------------------------------
    # Generic N-model comparison.
    # Quality first: efficiency is evaluated only among strict
    # quality-qualified models (model=100% AND service=100%)
    # and only when their critical outputs have 100% parity.
    # --------------------------------------------------------
    if len(models) >= 2:
        model_names = [str(model["name"]) for model in models]
        calls_by_model = {
            name: len(by_model.get(name, []))
            for name in model_names
        }
        model_pass_by_model = {
            name: numeric_sum(by_model.get(name, []), "model_case_pass")
            for name in model_names
        }
        service_pass_by_model = {
            name: numeric_sum(by_model.get(name, []), "service_case_pass")
            for name in model_names
        }

        service_qualified = [
            name for name in model_names
            if calls_by_model[name] > 0
            and service_pass_by_model[name] == calls_by_model[name]
        ]
        strict_qualified = [
            name for name in model_names
            if calls_by_model[name] > 0
            and model_pass_by_model[name] == calls_by_model[name]
            and service_pass_by_model[name] == calls_by_model[name]
        ]

        parity_fields = (
            "route",
            "needs_clarification",
            "direct_answer_request",
            "frustration_high",
            "derived_skill_rule",
            "derived_hint_strength",
            "policy_tools",
            "tool_policy_pass",
            "service_case_pass",
        )

        maps = {
            name: {
                str(row.get("question_id")): row
                for row in by_model.get(name, [])
            }
            for name in model_names
        }
        common_ids = sorted(
            set.intersection(*(set(maps[name]) for name in model_names))
            if model_names else set(),
            key=lambda x: int(x),
        )

        parity_ids: list[str] = []
        mismatch_ids: list[str] = []
        for qid in common_ids:
            reference = maps[model_names[0]][qid]
            same = all(
                all(
                    str(maps[name][qid].get(field, ""))
                    == str(reference.get(field, ""))
                    for field in parity_fields
                )
                for name in model_names[1:]
            )
            (parity_ids if same else mismatch_ids).append(qid)

        # Parity among strict-qualified candidates only.
        strict_common_ids: list[str] = []
        strict_mismatch_ids: list[str] = []
        if len(strict_qualified) >= 2:
            strict_common_ids = sorted(
                set.intersection(*(set(maps[name]) for name in strict_qualified)),
                key=lambda x: int(x),
            )
            for qid in strict_common_ids:
                reference = maps[strict_qualified[0]][qid]
                same = all(
                    all(
                        str(maps[name][qid].get(field, ""))
                        == str(reference.get(field, ""))
                        for field in parity_fields
                    )
                    for name in strict_qualified[1:]
                )
                if not same:
                    strict_mismatch_ids.append(qid)

        strict_parity_100 = (
            len(strict_qualified) >= 2
            and len(strict_common_ids) > 0
            and not strict_mismatch_ids
        )
        efficiency_eligible = strict_parity_100

        compare_names = strict_qualified if efficiency_eligible else model_names
        total_tokens_by_model = {
            name: float(numeric_sum(by_model.get(name, []), "total_tokens"))
            for name in compare_names
        }
        uncached_by_model = {
            name: float(numeric_sum(by_model.get(name, []), "uncached_prompt_tokens"))
            for name in compare_names
        }
        completion_reasoning_by_model = {
            name: float(
                numeric_sum(by_model.get(name, []), "completion_tokens")
                + numeric_sum(by_model.get(name, []), "reasoning_tokens")
            )
            for name in compare_names
        }
        avg_latency_by_model: dict[str, float] = {}
        p95_latency_by_model: dict[str, float] = {}
        for name in compare_names:
            vals = numeric_float_values(by_model.get(name, []), "latency_ms")
            avg_latency_by_model[name] = sum(vals) / len(vals) if vals else 0.0
            p95_latency_by_model[name] = percentile_nearest_rank(vals, 0.95)

        total_token_leader = lower_model_label(total_tokens_by_model)
        uncached_leader = lower_model_label(uncached_by_model)
        generation_leader = lower_model_label(completion_reasoning_by_model)
        avg_latency_leader = lower_model_label(avg_latency_by_model)
        p95_latency_leader = lower_model_label(p95_latency_by_model)

        efficiency_lead = "DEFER"
        if efficiency_eligible:
            if (
                total_token_leader == avg_latency_leader
                and total_token_leader not in {"TIE", "N/A"}
            ):
                efficiency_lead = total_token_leader
            else:
                efficiency_lead = "MIXED"

        lines.extend([
            "[Cross-model final decision]",
            f"- configured models: {len(model_names)}",
            "- service-qualified models: " + (", ".join(service_qualified) if service_qualified else "none"),
            "- strict quality-qualified models: " + (", ".join(strict_qualified) if strict_qualified else "none"),
            f"- all-model critical output parity: {len(parity_ids)}/{len(common_ids)}",
            "- all-model parity mismatch ids: " + (", ".join(mismatch_ids) if mismatch_ids else "none"),
            "- strict-candidate parity 100%: " + ("YES" if strict_parity_100 else "NO"),
            "- efficiency comparison eligible: " + ("YES" if efficiency_eligible else "NO"),
            "- lower total tokens: " + total_token_leader,
            "- lower uncached prompt tokens: " + uncached_leader,
            "- lower completion+reasoning tokens: " + generation_leader,
            "- lower average latency: " + avg_latency_leader,
            "- lower p95 latency: " + p95_latency_leader,
            "- operational efficiency lead: " + efficiency_lead,
            "",
            "[Decision rule]",
            "- SERVICE GATE 100%를 먼저 본다. MODEL GATE는 모델 해석능력 진단용으로 별도 유지한다.",
            "- 효율 비교는 최소 2개 모델이 model+service 100%이고 서로 critical output parity 100%일 때만 허용한다.",
            "- total token과 avg latency가 같은 모델에서 모두 낮을 때만 efficiency lead로 표시한다.",
            "- 오답 후 재시도 토큰/시간은 절감으로 인정하지 않는다. SDK retry=0, fallback 없음.",
            "- 실제 비용은 provider의 cached/uncached/input/output 가격정책을 별도로 적용해야 하므로 여기서는 추정하지 않는다.",
            "",
        ])

    path.write_text(
        "\n".join(lines),
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--preflight-detail", action="store_true")
    parser.add_argument("--ids", type=str, default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument(
        "--blind-final",
        action="store_true",
        help="정책/프롬프트/코드 동결 상태의 blind holdout 12문항 실행",
    )
    parser.add_argument(
        "--blind50-stage",
        type=int,
        choices=(1, 2, 3),
        default=None,
        help="동결된 Blind50의 stage 1/2/3 중 하나만 실행",
    )
    parser.add_argument(
        "--blind50-merge",
        action="store_true",
        help="stage1~3 결과를 API 호출 없이 blind50_final로 병합",
    )
    parser.add_argument(
        "--eval-name",
        type=str,
        default=None,
        help="results 하위 평가 폴더명. 미지정 시 문항 기준 자동 생성",
    )
    parser.add_argument("--yes", action="store_true")
    parser.add_argument(
        "--max-api-calls",
        type=int,
        default=DEFAULT_MAX_API_CALLS,
        help="실수 방지용 최대 API 호출 수. 기본 250",
    )
    parser.add_argument(
        "--recover-latest",
        action="store_true",
        help="API 호출 없이 가장 최근 benchmark CSV에서 report.txt만 복구",
    )
    args = parser.parse_args()

    load_dotenv(PROJECT_ROOT / ".env")

    models = load_models()
    dataset = load_dataset()
    blind_dataset = load_blind_dataset()
    blind50_dataset = load_blind50_dataset()
    blind50_manifest = load_blind50_manifest()

    preflight = run_preflight(dataset)

    blind50_actual_tools = set(
        discover_registered_tools_once()
    )
    blind50_scoring_passed, blind50_failures = (
        scoring_contract_self_test(
            blind50_dataset,
            blind50_actual_tools,
        )
    )

    static_prompt_for_freeze = build_static_prompt()
    blind50_freeze_errors = verify_blind50_freeze(
        static_prompt_for_freeze,
        blind50_manifest,
    )

    if (
        blind50_scoring_passed
        != BLIND50_CASE_COUNT
        or blind50_freeze_errors
    ):
        preflight["all_pass"] = False

    if args.check or args.preflight_detail:
        print_preflight(
            preflight,
            detail=args.preflight_detail,
        )
        print(
            "50-case Blind contract:",
            f"{blind50_scoring_passed}/{BLIND50_CASE_COUNT}",
        )
        print(
            "Blind50 freeze:",
            "PASS"
            if not blind50_freeze_errors
            else "FAIL",
        )

        if args.preflight_detail:
            if blind50_failures:
                print(
                    json.dumps(
                        blind50_failures,
                        ensure_ascii=False,
                        indent=2,
                    )
                )
            if blind50_freeze_errors:
                print(
                    json.dumps(
                        blind50_freeze_errors,
                        ensure_ascii=False,
                        indent=2,
                    )
                )
        return

    if args.blind50_merge:
        if not preflight["all_pass"]:
            raise RuntimeError(
                "PREFLIGHT/Blind50 freeze가 PASS가 아니므로 merge를 중단합니다."
            )

        csv_path, report_path = merge_blind50_results(
            models=models,
            dataset=blind50_dataset,
            manifest=blind50_manifest,
            static_prompt=static_prompt_for_freeze,
            preflight=preflight,
        )

        print("[Blind50 병합 완료 - API 호출 0회]")
        print("CSV :", csv_path)
        print("TXT :", report_path)
        return

    if args.recover_latest:
        if not preflight["all_pass"]:
            raise RuntimeError(
                "PREFLIGHT가 PASS가 아니므로 report 복구도 중단합니다."
            )

        RESULTS_DIR.mkdir(
            parents=True,
            exist_ok=True,
        )

        csv_candidates = sorted(
            list(RESULTS_DIR.glob("*/result.csv"))
            + list(RESULTS_DIR.glob("model_benchmark_*.csv")),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not csv_candidates:
            raise RuntimeError(
                "복구할 model_benchmark_*.csv 파일이 없습니다."
            )

        csv_path = csv_candidates[0]

        with csv_path.open(
            "r",
            encoding="utf-8-sig",
            newline="",
        ) as f:
            rows = list(csv.DictReader(f))

        if not rows:
            raise RuntimeError(
                f"CSV에 결과 행이 없습니다: {csv_path}"
            )

        question_ids: list[int] = []

        for row in rows:
            raw_id = str(
                row.get("question_id", "")
            ).strip()

            if not raw_id:
                continue

            qid = int(raw_id)

            if qid not in question_ids:
                question_ids.append(qid)

        by_id = {
            int(case["id"]): case
            for case in (
                dataset
                + blind_dataset
                + blind50_dataset
            )
        }

        active_dataset = [
            by_id[qid]
            for qid in question_ids
            if qid in by_id
        ]

        if not active_dataset:
            raise RuntimeError(
                "CSV의 question_id를 dataset과 매칭하지 못했습니다."
            )

        static_prompt = build_static_prompt()
        if csv_path.name == "result.csv":
            report_path = (
                csv_path.parent
                / "report.txt"
            )
        else:
            report_path = (
                csv_path.parent
                / f"{csv_path.stem}_report.txt"
            )

        write_report(
            path=report_path,
            models=models,
            dataset=active_dataset,
            rows=rows,
            static_prompt=static_prompt,
            preflight=preflight,
        )

        print("[REPORT 복구 완료 - API 호출 0회]")
        print("CSV :", csv_path)
        print("TXT :", report_path)
        return

    if not preflight["all_pass"]:
        raise RuntimeError(
            "FINAL READY PREFLIGHT가 100%가 아니므로 "
            "유료 API benchmark를 시작하지 않습니다."
        )

    special_modes = sum([
        int(args.blind_final),
        int(args.blind50_stage is not None),
    ])

    if special_modes > 1:
        raise RuntimeError(
            "--blind-final과 --blind50-stage는 동시에 사용할 수 없습니다."
        )

    if args.blind50_stage is not None:
        if args.ids is not None or args.limit is not None:
            raise RuntimeError(
                "--blind50-stage에서는 --ids/--limit을 함께 사용하지 않습니다."
            )

        active_dataset = select_blind50_stage(
            blind50_dataset,
            blind50_manifest,
            args.blind50_stage,
        )

        if args.eval_name is None:
            args.eval_name = (
                f"blind50_stage{args.blind50_stage}"
            )
    elif args.blind_final:
        if args.ids is not None or args.limit is not None:
            raise RuntimeError(
                "--blind-final에서는 --ids/--limit을 함께 사용하지 않습니다."
            )

        active_dataset = blind_dataset

        if args.eval_name is None:
            args.eval_name = "blind_final_12"
    else:
        active_dataset = select_dataset(
            dataset,
            args.ids,
            args.limit,
        )

    expected_calls = (
        len(active_dataset)
        * len(models)
    )

    if args.max_api_calls < 1:
        raise RuntimeError("--max-api-calls는 1 이상이어야 합니다.")
    if expected_calls > args.max_api_calls:
        raise RuntimeError(
            f"API 호출 안전장치 초과: expected={expected_calls}, limit={args.max_api_calls}"
        )

    static_prompt = static_prompt_for_freeze
    actual_tools = set(
        discover_registered_tools_once()
    )

    print("[실행 전]")
    print("PREFLIGHT: PASS")
    print("문항:", len(active_dataset))
    print(
        "IDs:",
        ",".join(
            str(case["id"])
            for case in active_dataset
        ),
    )
    print("모델:", len(models))
    print("총 API 호출:", expected_calls)
    print("static prompt chars:", len(static_prompt))
    print("full SKILL.md per-call: NO")
    print("model Tool selection: NO")
    print("Hard Guard: ON")
    print("SDK max_retries: 0")
    print("fallback: 없음")
    print("acceptance: 100% only")
    if args.blind50_stage is not None:
        dataset_mode = (
            f"BLIND50_STAGE_{args.blind50_stage}"
        )
        dataset_identity_path = (
            BLIND50_DATASET_PATH
        )
    elif args.blind_final:
        dataset_mode = "BLIND_HOLDOUT_12"
        dataset_identity_path = (
            BLIND_DATASET_PATH
        )
    else:
        dataset_mode = "ORIGINAL_30"
        dataset_identity_path = (
            DATASET_PATH
        )

    print(
        "dataset mode:",
        dataset_mode,
    )
    print(
        "dataset sha256:",
        sha256_bytes(
            dataset_identity_path.read_bytes()
        ),
    )
    print(
        "static prompt sha256:",
        sha256_text(static_prompt),
    )
    print(
        "runtime policy sha256:",
        sha256_bytes(
            RUNTIME_POLICY_PATH.read_bytes()
        ),
    )
    print(
        "result folder:",
        RESULTS_DIR / build_eval_name(active_dataset, args),
    )

    if not args.yes:
        answer = input(
            "\n실제 API 호출을 시작하려면 RUN 입력: "
        ).strip()

        if answer != "RUN":
            print(
                "취소했습니다. API 호출 없음."
            )
            return

    client = make_client()
    RESULTS_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    run_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    eval_name = build_eval_name(
        active_dataset,
        args,
    )
    eval_dir = RESULTS_DIR / eval_name
    eval_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    # 같은 평가를 다시 실행하면 이 두 파일만 갱신.
    # timestamp 파일을 계속 쌓지 않는다.
    csv_path = eval_dir / "result.csv"
    report_path = eval_dir / "report.txt"

    rows: list[dict[str, Any]] = []

    with csv_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as f:
        writer = csv.DictWriter(
            f,
            fieldnames=CSV_FIELDS,
        )
        writer.writeheader()
        f.flush()

        for model in models:
            name = str(model["name"])
            model_id = str(model["model"])

            print(
                f"\n[{name}] {model_id}"
            )

            for index, case in enumerate(
                active_dataset,
                start=1,
            ):
                payload = build_model_input(case)

                row = {
                    field: ""
                    for field in CSV_FIELDS
                }

                row.update({
                    "run_id": run_id,
                    "model_name": name,
                    "model_id": model_id,
                    "question_id": case["id"],
                    "category": case["category"],
                    "flow": case["flow"],
                })

                try:
                    # expected를 call_model에 전달하지 않음.
                    model_result = call_model(
                        client=client,
                        model_config=model,
                        static_prompt=static_prompt,
                        payload=payload,
                    )
                    row.update(model_result)

                    row.update(
                        score_case(
                            case=case,
                            payload=payload,
                            model_result=model_result,
                            actual_tools=actual_tools,
                        )
                    )
                except Exception as exc:
                    row.update({
                        "status": "API_ERROR",
                        "error_type": type(exc).__name__,
                        "error_message": str(exc)[:1000],
                    })

                writer.writerow(row)
                f.flush()
                rows.append(row)

                print(
                    f"  {index:02d}/{len(active_dataset)} "
                    f"id={case['id']} "
                    f"status={row['status']} "
                    f"model={row['model_case_pass'] or '-'} "
                    f"guard={row['guard_action'] or '-'} "
                    f"tool={row['tool_policy_pass'] or '-'} "
                    f"service={row['service_case_pass'] or '-'} "
                    f"tokens={row['total_tokens'] or '-'}"
                )

    write_report(
        path=report_path,
        models=models,
        dataset=active_dataset,
        rows=rows,
        static_prompt=static_prompt,
        preflight=preflight,
    )

    print("\n[완료]")
    print("CSV :", csv_path)
    print("TXT :", report_path)


if __name__ == "__main__":
    main()
