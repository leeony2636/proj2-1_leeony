"""공식 LLM 평가 전에 runtime에 평가셋 정답/문장 하드코딩이 섞였는지 정적 검사한다.

이 스크립트는 '정답을 잘 맞히는지'를 검사하지 않는다. 평가 데이터가 실제 Agent runtime으로
새어 들어가는 명백한 경로와 핵심질문 문장 복붙만 fail-closed로 잡는다.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_ROOTS = (ROOT / "backend" / "services", ROOT / "backend" / "routers", ROOT / "mcp_server")
# 비교용 baseline은 의도적으로 키워드 규칙을 가진다. 공식 OpenRouter 평가 runtime 정답 하드코딩으로 보지 않는다.
ALLOWED_COMPARISON_FILES = {ROOT / "backend" / "services" / "baseline_router.py"}
FORBIDDEN_RUNTIME_MARKERS = (
    "service_expected",
    "core30_quality_contract",
    "human_validated",
    "reviewer",
    "evals/dataset.jsonl",
)


def _load_rows(dataset: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in dataset.read_text(encoding="utf-8").splitlines() if line.strip()]


def _runtime_files() -> list[Path]:
    files: list[Path] = []
    for root in RUNTIME_ROOTS:
        if not root.exists():
            continue
        files.extend(path for path in root.rglob("*.py") if path not in ALLOWED_COMPARISON_FILES)
    return sorted(files)


def audit_runtime(dataset: Path) -> dict[str, Any]:
    rows = _load_rows(dataset)
    runtime_files = _runtime_files()
    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    # 평가 전용 키/파일을 runtime이 직접 참조하면 정답 누수 가능성이 있으므로 실패.
    for path in runtime_files:
        text = path.read_text(encoding="utf-8", errors="replace")
        rel = str(path.relative_to(ROOT))
        for marker in FORBIDDEN_RUNTIME_MARKERS:
            if marker in text:
                violations.append({"type": "EVAL_MARKER_IN_RUNTIME", "file": rel, "marker": marker})
        if "from evals" in text or "import evals" in text:
            violations.append({"type": "EVAL_IMPORT_IN_RUNTIME", "file": rel, "marker": "evals import"})

    # 핵심질문 원문을 production runtime에 그대로 복붙해 분기하는지 검사한다.
    corpus = {path: path.read_text(encoding="utf-8", errors="replace") for path in runtime_files}
    for row in rows:
        utterance = str((row.get("input") or {}).get("utterance") or row.get("utterance") or "").strip()
        if len(utterance) < 12:
            continue
        # 완전 일치만 fail: 일반 도메인 용어가 우연히 겹치는 것은 하드코딩으로 오판하지 않는다.
        for path, text in corpus.items():
            if utterance in text:
                violations.append(
                    {
                        "type": "EVAL_UTTERANCE_LITERAL_IN_RUNTIME",
                        "file": str(path.relative_to(ROOT)),
                        "marker": f"case:{row.get('id')}",
                    }
                )

    # llm.py가 baseline을 비교용으로 import하는 것은 현재 구조상 허용하지만 공식 runner가 openrouter만 쓰는지 별도 확인한다.
    llm_path = ROOT / "backend" / "services" / "llm.py"
    if llm_path.exists() and "classify_intent_baseline" in llm_path.read_text(encoding="utf-8"):
        warnings.append(
            {
                "type": "BASELINE_PRESENT_COMPARISON_ONLY",
                "file": "backend/services/llm.py",
                "note": "공식 모델선정 runner는 provider=openrouter로만 실행해야 한다.",
            }
        )

    return {
        "status": "PASS" if not violations else "FAIL",
        "dataset": str(dataset),
        "runtime_files_scanned": len(runtime_files),
        "violations": violations,
        "warnings": warnings,
        "note": "정적 누수 검사다. 일반 Domain Skill/Policy 규칙 자체는 정답 하드코딩으로 보지 않는다.",
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="evals/dataset.jsonl")
    args = parser.parse_args()
    report = audit_runtime(Path(args.dataset))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if report["status"] != "PASS":
        raise SystemExit(2)


if __name__ == "__main__":
    main()
