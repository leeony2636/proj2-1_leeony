# 평가 계획

## 1. 평가 종류를 분리한다

| 구분 | 목적 | 현재 상태 |
|---|---|---|
| 계획서 보완 10문항 | 도메인 경험자가 정상3/경계4/실패3의 정답과 이유를 직접 판정 | 팀 작성 필요 |
| Domain Dataset 30건 이상 | 실제 LLM의 맥락 이해/도구 선택/도메인 판단 품질 측정 | 기존 30건은 합성 seed, 사람 Ground Truth 미확정 |
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
# 합성 seed로 전체 서비스 경로 smoke. 실제 도메인 품질 점수가 아님
python evals/run_llm_eval.py \
  --provider baseline \
  --dataset evals/dataset.jsonl \
  --output evals/results/baseline_service_flow.json

# 실제 Provider: 비용/외부 호출을 확인한 뒤 명시적으로 허용
python evals/run_llm_eval.py \
  --provider openrouter \
  --allow-external-llm \
  --dataset evals/human_domain_eval.jsonl \
  --output evals/results/openrouter_service_flow.json
```

Langfuse 외부 전송은 평가 실행기에서 기본 차단한다. 필요한 경우 별도 승인 후 `--allow-observability-export`를 사용한다.

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

사람이 품질 정답으로 채점할 row에는 최소한 아래 정보가 필요하다.

- `human_validated: true`
- 실제 서비스 입력 원문
- `service_expected`에 평가할 `lookup_tools`, `completed_actions`, `final_status` 등 필요한 항목
- 판정 이유
- 판정자와 해당 도메인 경험 근거

LLM이 평가 입력·정답·판정 이유를 대신 만들지 않는다.

## 7. 개선 전후 비교

동일 입력/동일 판정 기준으로 다음을 분리해 비교한다.

1. baseline vs 실제 LLM
2. 구조 전체 변경 전후
3. 개별 Prompt/Skill version 변경 전후
4. raw 계약 준수 vs 정규화 후 통과

여러 변경을 한 번에 적용한 결과를 특정 프롬프트 한 줄의 효과라고 해석하지 않는다.
