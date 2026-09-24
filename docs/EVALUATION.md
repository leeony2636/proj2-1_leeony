# 평가 계획

## 1. 평가 종류를 분리한다

| 구분 | 목적 | 현재 상태 |
|---|---|---|
| 현재 core-30 | normal 10 / boundary 12 / failure 8, 30건 모두 `human_validated=true` | 모델 선정 정본 |
| Evaluator 품질 계약 | Agent 입력과 분리된 `core30_quality_contract.json`으로 구조적 기대조건 + 사람 의미검토 구분 | 구현됨 |
| 정규화 기술 테스트 100건 | 합성 payload가 enum/action/lookup 정규화 계약으로 안전하게 정리되는지 확인 | `test_llm_normalization_matrix.py` 100 case 구현/통과 |
| 실제 모델 계약 측정 | 정규화 전 원응답 계약 준수와 정규화 후 통과를 분리 측정 | 실행 도구만 준비, 실제 100건 미실행 |
| 서비스 흐름 평가 | INITIAL → 선택 조회 → FOLLOWUP → 실제 처리 → 최종 안내 평가 | 격리 실행기 구현, baseline 30건 smoke 실행 |

## 2. 기술 검증 축

- 구조화 결과 enum/schema
- 허용 lookup/action
- 세션/팀 격리
- 승인 힌트와 AnswerVault 경계
- 상태 전이/idempotency
- lookup 결과가 후속 LLM context에 전달되는지
- 질문 전환 시 부작용이 실행되지 않는지
- 부분 처리/오류/재시도
- 실제 처리 결과와 최종 안내의 구조적 모순 여부

기술 테스트 통과는 실제 언어 이해 품질을 의미하지 않는다.

## 3. 실제 LLM 평가 축

- 맥락 이해
- 독립 복합 요청 vs 동일 문제의 원인 구분
- 추가 질문 필요성과 질문의 적절성
- `get_hint_history` / `get_master_request_status` 선택
- 조회 결과에 따른 후속 action 변화
- Domain Skill 기준 적용의 올바름
- `support_need` 적절성
- 직원 전달 facts/attempts/unknowns의 사실성
- 실제 처리와 최종 안내의 의미상 일치
- latency / token / provider-reported cost

자동으로 판정하기 어려운 질문 적절성, 직원 전달 사실성, Skill 규칙의 올바른 적용, 최종 안내 의미 일치는 사람 검토로 남긴다.

## 4. 서비스 흐름 평가 실행기

`evals/run_llm_eval.py`는 운영 데이터와 분리된 MemoryRuntime을 사용한다. 평가 세션, 힌트 이력, 운영 요청, 대화 이력은 평가 런타임에만 저장된다.

```bash
# 외부 호출 없는 구조 smoke
python evals/run_llm_eval.py \
  --provider baseline \
  --dataset evals/dataset.jsonl \
  --output evals/results/live_runs/offline_baseline_30.json

# 공식 4모델 선정은 별도 runner 사용
python evals/run_model_selection.py \
  --allow-external-llm \
  --allow-observability-export \
  --confirm-dedicated-key-cap
```

공식 모델 선정은 `evals/TEST_POLICY.md`를 따른다. OpenRouter 유료 후보 4개 전체의 누적 선정 테스트 상한은 `$5.00`이며 각 모델당 `$5`가 아니다. 코드가 모든 요청에 `provider.zdr=true`와 `data_collection=deny`를 강제하고, 네 exact model ID가 최신 ZDR filtered catalog에 모두 존재해야 inference를 시작한다. 비용 미보고/Provider 호출 오류면 다음 사례·모델로 진행하지 않는다. 최종 하드 상한은 OpenRouter 전용 테스트 key spending limit `$5 이하`로 보완한다.

Langfuse 기록을 켠 공식 실행은 유료 inference 전에 safe preflight event 전송이 성공해야 한다. 원문 고객 발화·정답·힌트 본문·API key는 Langfuse allowlist 밖에 둔다.

### 팀이 채울 최소 항목과 실행 순서

1. `evals/TEST_POLICY.md`와 `evals/model_selection_policy.json`이 **현재 기준**이다. $30은 프로젝트 전체 참고 예산, 이번 4모델 선정 단계는 총 $5다.
2. 팀이 `evals/dataset.jsonl` 30건과 `evals/core30_quality_contract.json`의 기대 흐름을 확인한다. `evals/quality_contract_approval.json`에 현재 두 SHA-256, `approved_case_ids` 1~30, 실제 검토자와 검토 근거, `approval_status: "APPROVED"`를 기록한다. 기본값은 승인 대기이며 코드가 대신 승인하지 않는다. 수정된 데이터/계약의 hash가 바뀌면 다시 승인한다.
3. 로컬 `.env` 또는 프로세스 환경에 `OPENROUTER_API_KEY`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`를 설정한다. 키를 저장소나 평가 JSON에 넣지 않는다. 후보 4개 ID는 `evals/model_candidates.example.json`에서 확인/수정하거나 `OPENROUTER_MODELS`로 지정한다. 실행 시 ZDR filtered catalog와 가격을 새로 검사한다.
4. 비용을 쓰지 않고 `python evals/run_model_comparison.py --offline-only`와 `python -m pytest backend/tests -q`를 실행한다. 전용 OpenRouter 키에 $5 이하의 hard spending limit을 직접 설정한다.
5. `python evals/run_model_selection.py --allow-external-llm --allow-observability-export --confirm-dedicated-key-cap`를 실행한다. Langfuse 인증과 안전한 사전 기록이 실패하면 유료 호출 전 중지한다. 사례 이벤트나 숫자 점수 전송이 실패하면 그 모델의 다음 사례를 중지한다. 각 모델의 원문 포함 JSON은 `evals/results/live_runs/`에 임시 보관되고 Git에서 제외된다. 비교용 사례 CSV는 `evals/results/model_selection_csv/`에 생성된다.
6. `evals/results/live_runs/model_selection/`의 각 모델 JSON을 **복사**하여 `evals/MODEL_REVIEW_RUBRIC.md`를 기준으로 `results[].project_model_capability_scorecard.review_record`를 팀이 채운다. 30건 모두 `status: "REVIEWED"`, reviewer, 적용 가능한 여섯 사람 평가축의 `ratings` (`PASS`/`PARTIAL`/`FAIL`)과 각 축의 사례별 `evidence`, `hard_fail_triggered`를 기록한다. Observation이 실제로 없을 때만 `NOT_APPLICABLE`을 허용한다. 23건은 도메인 의미 계약상 필수 사람 검토이고, 8축 모델 판단 비교는 30건 모두 검토한다. 근거를 지어내지 않는다.
7. 각 모델에 대해 `python evals/score_reviewed_results.py --input <검토한 모델 결과.json> --output <집계.json> --csv-output evals/results/model_selection_csv/<model>-review.csv --publish-langfuse`를 실행한다. `QUALITY_PASS`는 30/30 완료, 자동 hard fail 0, 최종 계약 30/30, 적용 가능한 사람 평가축 모두 PASS를 의미한다. `PARTIAL`이나 미검토는 합격이 아니다. 사례별 숫자 Score가 같은 Langfuse trace ID에 저장되며 CSV에는 점수·상태·측정값만 남고 원문과 사람의 서술 근거는 로컬 검토 파일에만 남는다.

결과 JSON에는 `selection_run_id`, `evaluation_run_id`, dataset/계약 hash, 모델 ID, 사례별 `langfuse_trace_id`가 기록된다. Langfuse 화면에서 해당 trace와 `core30_auto_contract`, `structured_output_stability`, `hard_fail_auto_guard`, 사람 검토 점수를 대조한다. `hard_fail_auto_guard`는 자동 스포일러 가드만 뜻하며 **전체 보안 무결성 합격을 뜻하지 않는다**. 실제 키가 없는 환경에서는 SDK 모의 테스트까지만 가능하며 대시보드 저장 여부는 실연결 후 확인해야 한다.

## 5. 실제 모델 계약 측정

`evals/run_model_contract_eval.py`는 실제 모델의 정규화 전 JSON 계약 준수와 정규화 후 결과를 구분한다. 기본은 100개 입력이 있어야 실행한다.

```bash
python evals/run_model_contract_eval.py \
  --dataset evals/approved_contract_inputs.jsonl \
  --required-cases 100 \
  --allow-external-llm \
  --retry-invalid-contract \
  --output evals/results/model_contract_100.json
```

- 입력이 100건 미만이면 횟수를 맞추기 위해 새 도메인 정답을 생성하지 않고 `NOT_RUN_INSUFFICIENT_EVAL_INPUTS`로 종료한다.
- 외부 호출 승인이 없으면 `NOT_RUN_EXTERNAL_LLM_APPROVAL_REQUIRED`로 기록한다.
- 첫 응답의 raw 계약 위반, 정규화 변경 필드, 재시도 raw 계약 준수를 따로 기록한다.
- 이 결과는 도메인 의미 품질 점수가 아니다.

## 6. 사람이 검증한 row 최소 계약

현재 core-30은 `human_validated=true`와 reviewer/expected 설명을 유지한다. 자동으로 안전하게 판정할 수 있는 항목은 `evals/core30_quality_contract.json`에 구조화하고, 의미 해석이 필요한 항목은 `human_review_required=true`로 남긴다. 이 evaluator 전용 계약은 Agent 입력에 전달하지 않는다.

LLM이 평가 정답·판정 이유를 대신 만들거나 Runtime이 case ID/평가 발화를 보고 정답으로 분기하지 않는다.

## 7. 개선 전후 비교

동일 입력/동일 판정 기준으로 다음을 분리해 비교한다.

1. baseline vs 실제 LLM
2. 구조 전체 변경 전후
3. 개별 Prompt/Skill version 변경 전후
4. raw 계약 준수 vs 정규화 후 통과

여러 변경을 한 번에 적용한 결과를 특정 프롬프트 한 줄의 효과라고 해석하지 않는다.
