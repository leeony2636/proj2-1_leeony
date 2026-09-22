"""LLM 입력에 사용하는 Domain Skill의 버전/적용 범위를 관리한다.

전체 SKILL.md를 매 요청마다 넣지 않고, 현재 서비스에서 실제로 쓰는 확정 경계와
현장 판단 참고 기준만 구조화해 전달한다. 미확정 정책은 실행 기준에서 제외한다.

`applied_skill_rules`는 LLM의 자기보고 값이다. 아래의 ID 필터는 존재하는 rule id만
남기는 기술 검증이며, 실제 규칙을 올바르게 적용했다는 의미 품질 검증이 아니다.
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "skills" / "domain_policy.json"


@lru_cache(maxsize=1)
def load_domain_policy() -> dict:
    data = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    required = {
        "version",
        "confirmed_boundaries",
        "llm_guidance",
        "unconfirmed_policies",
        "visibility_legend",
        "reporting_semantics",
    }
    missing = sorted(required - set(data))
    if missing:
        raise ValueError(f"DOMAIN_POLICY_MISSING_FIELDS:{','.join(missing)}")
    return data


def build_llm_skill_context() -> dict:
    """LLM이 판단에 실제 사용할 compact Skill context를 반환한다."""
    data = load_domain_policy()
    return {
        "version": data["version"],
        "confirmed_boundaries": data["confirmed_boundaries"],
        "llm_guidance": data["llm_guidance"],
        "unconfirmed_policy_ids": [item["id"] for item in data["unconfirmed_policies"]],
        "visibility_legend": data["visibility_legend"],
        "reporting_semantics": data["reporting_semantics"],
        "instruction": (
            "confirmed_boundaries는 반드시 지키고, llm_guidance는 판단 참고 기준으로 사용할 수 있다. "
            "unconfirmed_policy_ids는 팀 확정 전이므로 자동 실행 기준으로 사용하지 않는다. "
            "visibility=INTERNAL_ONLY인 내부 값·메타데이터는 고객 안내에 직접 노출하지 않는다. "
            "applied_skill_rules에는 실제 판단에 사용했다고 스스로 보고하는 rule id만 적되, "
            "이 값은 준수 증명이 아니라 평가용 자기보고 메타데이터다."
        ),
    }


def domain_policy_version() -> str:
    return str(load_domain_policy()["version"])


def _allowed_reportable_rule_ids() -> set[str]:
    data = load_domain_policy()
    allowed = {item["id"] for item in data["confirmed_boundaries"]}
    allowed.update(item["id"] for item in data["llm_guidance"])
    return allowed


def filter_reported_skill_rule_ids(rule_ids: list[str]) -> list[str]:
    """LLM이 보고한 rule id 중 현재 Skill에 실제 존재하는 ID만 남긴다.

    주의: 이 함수는 ID 존재만 확인한다. 규칙의 올바른 적용 여부는 평가 항목이다.
    """
    allowed = _allowed_reportable_rule_ids()
    result: list[str] = []
    for rule_id in rule_ids:
        if rule_id in allowed and rule_id not in result:
            result.append(rule_id)
    return result


# 기존 호출부 호환용 alias. 이름과 달리 의미 준수 검증은 하지 않는다.
def validate_applied_rule_ids(rule_ids: list[str]) -> list[str]:
    return filter_reported_skill_rule_ids(rule_ids)
