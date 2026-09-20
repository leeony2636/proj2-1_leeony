# Team Project Integration Guide

이 Benchmark 저장소는 개인 GitHub에서 **기준 테스트/모델 비교 로직**으로 보관하고, 팀 프로젝트에는 필요한 부분만 반영하기 위한 구조입니다.

## 1. 기준 데이터

- `evals/dataset.jsonl` = **Core30 기준셋**
  - normal 10 / boundary 12 / failure 8
  - 서비스 규칙 변경 여부를 확인하는 회귀 기준
- `evals/dataset_blind50.jsonl` = **Blind50 모델 비교군**
  - normal 17 / boundary 20 / failure 13
  - 새 모델을 같은 조건에서 비교하기 위한 holdout
  - `evals/blind50_manifest.json`의 hash로 데이터/정책/프롬프트를 동결

Core30과 Blind50은 서로 목적이 다르므로 합쳐서 하나의 점수로 만들지 않습니다. Core30은 기준 계약, Blind50은 새 표현에 대한 일반화/모델 비교입니다.

## 2. 개인 GitHub에 유지할 것

아래는 벤치마크의 원본 기준으로 유지합니다.

- `evals/run_model_benchmark.py`
- `evals/dataset.jsonl`
- `evals/dataset_blind50.jsonl`
- `evals/blind50_manifest.json`
- `evals/runtime_policy.json`
- `evals/skill_policy.py`
- `evals/tool_policy.py`
- `evals/hard_guard.py`
- `history/`
- `reference_results/`

## 3. 팀 프로젝트에 반영할 것

팀 프로젝트에서 현재 서비스 구조와 맞는 경우 다음을 반영합니다.

- `evals/` 테스트 하네스
- `skill_policy.py`의 deterministic Skill 판단
- `tool_policy.py`의 deterministic Tool 계획
- `hard_guard.py`의 fail-closed 보호 로직
- `runtime_policy.json`의 route/경계 정의

단, 팀 프로젝트의 실제 `backend/services/llm.py`, `mcp_server/server.py`, DB schema와 충돌하지 않는지 확인한 뒤 적용합니다. 이 ZIP은 팀 저장소에 자동으로 commit/push/merge하지 않습니다.

## 4. 새 모델 비교 절차

1. `evals/benchmark_models.json`에 후보 모델을 추가/교체
2. `python .\evals\run_model_benchmark.py --check`
3. Core30으로 기준 계약 확인
4. Blind50 stage 1 → 2 → 3 실행
5. `--blind50-merge`로 API 호출 없이 최종 병합
6. SERVICE 품질이 먼저이며, 동등 품질 후보끼리만 token/latency 비교

모델 목록은 바꿀 수 있지만 Blind50 데이터와 frozen policy/prompt/code는 바꾸지 않습니다. 바꿔야 한다면 Blind50 v2처럼 새 버전을 만듭니다.

## 5. 결과 해석 원칙

- `MODEL GATE`: 모델 자체의 route/boolean signal/schema 해석능력
- `SERVICE GATE`: HardGuard가 반영된 effective route + SkillPolicy + ToolPolicy 기준 실제 서비스 경로
- 첫 호출이 틀려 재시도하면 첫 오답 호출의 token/latency도 실제 비용으로 계산
- 정확도가 다르면 token 절감만으로 모델을 선택하지 않음

## 6. 현재 reference

현재 동결 Blind50 reference에서는 GPT-5.4 mini가 service 46/50, GPT-5.6 Luna가 service 50/50을 기록했습니다. 이 값은 모델의 범용 능력 전체가 아니라 **현재 방탈출 Agent 정책/프롬프트/데이터 범위에서의 reference**입니다.
