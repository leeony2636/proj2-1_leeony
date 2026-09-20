"""Cached policy/runtime sources for V4.4."""
from __future__ import annotations

import ast
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EVAL_DIR = PROJECT_ROOT / "evals"
SKILL_PATH = PROJECT_ROOT / "skills" / "SKILL.md"
RUNTIME_POLICY_PATH = EVAL_DIR / "runtime_policy.json"
MCP_SERVER_PATH = PROJECT_ROOT / "mcp_server" / "server.py"

REQUIRED_MCP_TOOLS = {
    "get_game_session",
    "get_puzzle_context",
    "get_hint_history",
    "get_approved_hint",
    "report_equipment_issue",
    "request_game_master",
}


@lru_cache(maxsize=1)
def load_system_prompt_once() -> str:
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from backend.services.llm import SYSTEM_PROMPT  # type: ignore

    value = str(SYSTEM_PROMPT).strip()

    if not value:
        raise RuntimeError("SYSTEM_PROMPT가 비어 있습니다.")

    return value


@lru_cache(maxsize=1)
def load_skill_once() -> str:
    if not SKILL_PATH.exists():
        raise RuntimeError(
            f"SKILL.md가 없습니다: {SKILL_PATH}"
        )

    value = SKILL_PATH.read_text(encoding="utf-8").strip()

    if not value:
        raise RuntimeError("SKILL.md가 비어 있습니다.")

    return value


@lru_cache(maxsize=1)
def load_runtime_policy_once() -> dict[str, Any]:
    value = json.loads(
        RUNTIME_POLICY_PATH.read_text(encoding="utf-8")
    )

    if value.get("version") != "final-ready-clean-v2":
        raise RuntimeError(
            "runtime_policy.json version != final-ready-clean-v2"
        )

    return value


@lru_cache(maxsize=1)
def discover_registered_tools_once() -> tuple[str, ...]:
    if not MCP_SERVER_PATH.exists():
        raise RuntimeError(
            f"MCP server.py가 없습니다: {MCP_SERVER_PATH}"
        )

    source = MCP_SERVER_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)

    names: list[str] = []

    # 현재 프로젝트 방식:
    # for tool in (...):
    #     mcp.tool()(tool)
    for node in ast.walk(tree):
        if not isinstance(node, ast.For):
            continue

        if not isinstance(node.target, ast.Name):
            continue

        loop_var = node.target.id
        registered = False

        for child in ast.walk(node):
            if not isinstance(child, ast.Call):
                continue

            inner = child.func

            if not isinstance(inner, ast.Call):
                continue

            if not isinstance(inner.func, ast.Attribute):
                continue

            if inner.func.attr != "tool":
                continue

            if len(child.args) != 1:
                continue

            arg = child.args[0]

            if isinstance(arg, ast.Name) and arg.id == loop_var:
                registered = True
                break

        if (
            registered
            and isinstance(node.iter, (ast.Tuple, ast.List))
        ):
            for item in node.iter.elts:
                if isinstance(item, ast.Name):
                    names.append(item.id)

    names = sorted(set(names))

    if not names:
        raise RuntimeError(
            "실제 FastMCP Tool 등록을 찾지 못했습니다."
        )

    return tuple(names)


def _contains_all(text: str, words: tuple[str, ...]) -> bool:
    return all(word in text for word in words)


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(word in text for word in words)


def _concept(
    text: str,
    *groups: tuple[str, ...],
) -> bool:
    """각 그룹에서 하나 이상 발견되면 같은 개념으로 인정한다.

    문서 표현 차이(예: 게임마스터/직원/관리자, 기구/소품/장비)가
    정책 오류로 오인되지 않게 한다.
    """
    normalized = " ".join(text.lower().split())

    return all(
        any(alias.lower() in normalized for alias in group)
        for group in groups
    )


def validate_skill_contract(
    skill_text: str,
    policy: dict[str, Any],
) -> list[str]:
    """SKILL.md의 필수 의미가 compact runtime policy에 보존됐는지 검사.

    문구 exact match가 아니라 개념 단위로 검사한다.
    """
    errors: list[str] = []
    safety = policy.get("mandatory_safety", [])
    hint_rules = policy.get("hint_rules", {})
    constraints = policy.get("runtime_constraints", {})

    # 1) 우선순위
    expected_priority = [
        "ANSWER_REQUEST",
        "RE_REQUEST_OVERRIDE",
        "EMOTION_OVERRIDE",
        "BASE_RULE_TIME_AND_PROGRESS",
        "BASE_RULE_DEFAULT",
    ]
    if (
        not _concept(
            skill_text,
            ("정답",),
            ("재요청",),
            ("감정",),
            ("기본규칙", "기본 규칙"),
        )
        or policy.get("hint_priority") != expected_priority
    ):
        errors.append("hint_priority")

    # 2) 시간/진도 기본 규칙
    if not (
        "15" in skill_text
        and "50" in skill_text
        and "BASE_RULE_TIME_AND_PROGRESS" in hint_rules
        and "BASE_RULE_DEFAULT" in hint_rules
    ):
        errors.append("time_progress_threshold")

    # 3) 정답 직접 노출 금지
    if not (
        _concept(
            skill_text,
            ("정답",),
            ("말로", "직접", "먼저"),
        )
        and any(
            ("정답" in item)
            and _contains_any(
                item,
                ("노출 금지", "직접 노출 금지", "raw_solution", "answer_key"),
            )
            for item in safety
        )
    ):
        errors.append("answer_protection")

    # 4) 기구/소품 이상 -> 직원 경로
    skill_equipment_ok = _concept(
        skill_text,
        ("기구", "소품", "장비", "자물쇠", "오작동", "고장"),
        (
            "게임마스터",
            "직원",
            "관리자",
            "master_request",
            "request_game_master",
            "호출",
            "넘긴다",
        ),
    )
    policy_equipment_ok = any(
        _contains_any(
            item,
            ("기구", "소품", "장비", "자물쇠", "오작동", "고장"),
        )
        and _contains_any(
            item,
            (
                "request_game_master",
                "게임마스터",
                "직원",
                "관리자",
                "직원 경로",
                "호출",
            ),
        )
        for item in safety
    )
    if not (skill_equipment_ok and policy_equipment_ok):
        errors.append("equipment_exception")

    # 5) 진도 모호 -> 확인 질문
    if not (
        _concept(
            skill_text,
            ("모호",),
            ("확인", "직접 물", "질문"),
        )
        and any(
            ("모호한 진도" in item)
            and _contains_any(item, ("확인", "질문"))
            for item in safety
        )
    ):
        errors.append("ambiguous_progress")

    # 6) 테마 격리
    if not (
        "다른 테마" in skill_text
        and any("다른 테마" in item for item in safety)
    ):
        errors.append("cross_theme")

    # 7) 미도달 문제 스포일러
    if not (
        _contains_any(
            skill_text,
            ("아직 도달", "순서부터", "스포일러"),
        )
        and any(
            _contains_any(item, ("도달하지 않은", "스포일러"))
            for item in safety
        )
    ):
        errors.append("future_puzzle")

    # 8) 이번 2차 프로젝트 금지조건
    must_be_false = (
        "dynamic_skill_retrieval",
        "vector_embedding_lookup",
        "rag_enabled",
        "model_selects_tools",
        "model_decides_skill_rule",
        "model_decides_final_hint_strength",
        "full_skill_sent_each_call",
        "expected_data_visible_to_model",
    )
    for key in must_be_false:
        if constraints.get(key) is not False:
            errors.append(f"constraint_{key}")

    if constraints.get("static_sources_loaded_once_per_process") is not True:
        errors.append("constraint_static_sources_loaded_once_per_process")

    if constraints.get("fixed_prompt_prefix_for_provider_cache") is not True:
        errors.append("constraint_fixed_prompt_prefix_for_provider_cache")

    return errors

def skill_contract_diagnostics(
    skill_text: str,
    policy: dict[str, Any],
) -> dict[str, Any]:
    safety = policy.get("mandatory_safety", [])

    return {
        "equipment_source_object_term": _contains_any(
            skill_text,
            ("기구", "소품", "장비", "자물쇠", "오작동", "고장"),
        ),
        "equipment_source_escalation_term": _contains_any(
            skill_text,
            (
                "게임마스터",
                "직원",
                "관리자",
                "MASTER_REQUEST",
                "request_game_master",
                "호출",
                "넘긴다",
            ),
        ),
        "equipment_policy_object_and_escalation": any(
            _contains_any(
                item,
                ("기구", "소품", "장비", "자물쇠", "오작동", "고장"),
            )
            and _contains_any(
                item,
                (
                    "request_game_master",
                    "게임마스터",
                    "직원",
                    "관리자",
                    "직원 경로",
                    "호출",
                ),
            )
            for item in safety
        ),
        "rag_disabled": (
            policy.get("runtime_constraints", {}).get("rag_enabled") is False
            and policy.get("runtime_constraints", {}).get("dynamic_skill_retrieval") is False
            and policy.get("runtime_constraints", {}).get("vector_embedding_lookup") is False
        ),
        "model_tool_selection_disabled": (
            policy.get("runtime_constraints", {}).get("model_selects_tools") is False
        ),
        "full_skill_per_call_disabled": (
            policy.get("runtime_constraints", {}).get("full_skill_sent_each_call") is False
        ),
    }

def validate_mcp_contract(
    actual_tools: set[str],
) -> list[str]:
    missing = sorted(
        REQUIRED_MCP_TOOLS - actual_tools
    )
    return missing


def cache_stats() -> dict[str, dict[str, int | None]]:
    funcs = {
        "system_prompt": load_system_prompt_once,
        "skill": load_skill_once,
        "runtime_policy": load_runtime_policy_once,
        "tool_registry": discover_registered_tools_once,
    }

    result = {}

    for name, func in funcs.items():
        info = func.cache_info()
        result[name] = {
            "hits": info.hits,
            "misses": info.misses,
            "maxsize": info.maxsize,
            "currsize": info.currsize,
        }

    return result
