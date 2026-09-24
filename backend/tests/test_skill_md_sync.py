"""SKILL.md와 skills/domain_policy.json의 id 인용이 서로 어긋나지 않는지 검증한다.

수정 사유: SKILL.md(사람이 읽는 원본)가 domain_policy.json(실제 LLM 입력)과 오랫동안
따로 놀아 숫자 힌트 강도 규칙이 '미확정'인데도 본문엔 '기본규칙'처럼 서술돼 있던 사고가
있었다. 이 테스트는 13강 "할루시네이션과 근거 요구"의 citation verification을 코드로
고정한 것이다 — 근거를 요구했다고 끝나지 않고, 그 근거가 실재하는지 코드가 다시 확인한다.
사람이 수동으로 대조하지 않아도, 둘 중 하나만 고치고 나머지를 안 고치면 이 테스트가 실패한다.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL_MD = ROOT / "skills" / "SKILL.md"
POLICY_JSON = ROOT / "skills" / "domain_policy.json"

_ID_PATTERN = re.compile(r"`([A-Z][A-Z0-9_]{2,})`")
_POLICY_GROUPS = ("confirmed_boundaries", "llm_guidance", "unconfirmed_policies")


def _load_policy() -> dict:
    return json.loads(POLICY_JSON.read_text(encoding="utf-8"))


def _policy_ids(policy: dict) -> set[str]:
    ids: set[str] = set()
    for group in _POLICY_GROUPS:
        for item in policy[group]:
            ids.add(item["id"])
    return ids


def _policy_status_values(policy: dict) -> set[str]:
    # status/policy_status 값(CONFIRMED_BOUNDARY, DECIDED_NOT_ADOPTED 등)은 id가 아니라
    # 상태값이다. SKILL.md 본문에서 설명용으로 backtick을 써도 id로 오인하지 않는다.
    values: set[str] = set()
    for group in _POLICY_GROUPS:
        for item in policy[group]:
            for key in ("status", "policy_status"):
                if key in item:
                    values.add(item[key])
    return values


def _skill_md_backtick_ids(status_values: set[str]) -> set[str]:
    text = SKILL_MD.read_text(encoding="utf-8")
    candidates = set(_ID_PATTERN.findall(text))
    return candidates - status_values


def test_skill_md_only_cites_ids_that_exist_in_domain_policy() -> None:
    """SKILL.md가 인용하는 대문자 id는 domain_policy.json에 실재해야 한다 (근거 검증)."""
    policy = _load_policy()
    policy_ids = _policy_ids(policy)
    status_values = _policy_status_values(policy)
    skill_ids = _skill_md_backtick_ids(status_values)

    unknown = skill_ids - policy_ids
    assert not unknown, (
        "SKILL.md가 domain_policy.json에 없는 id를 인용했다(오타이거나 지어낸 근거일 수 있음): "
        f"{sorted(unknown)}"
    )


def test_domain_policy_ids_are_documented_in_skill_md() -> None:
    """domain_policy.json의 모든 id는 SKILL.md에 최소 한 번 문서화돼야 한다 (역방향 드리프트 방지)."""
    policy = _load_policy()
    policy_ids = _policy_ids(policy)
    status_values = _policy_status_values(policy)
    skill_ids = _skill_md_backtick_ids(status_values)

    undocumented = policy_ids - skill_ids
    assert not undocumented, (
        "domain_policy.json에는 있는데 SKILL.md에 문서화되지 않은 id: "
        f"{sorted(undocumented)}"
    )
