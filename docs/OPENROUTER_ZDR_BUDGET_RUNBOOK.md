# OpenRouter ZDR · 4모델 선정 · $5 상한 실행 절차

기준일: 2026-09-24. 이 문서는 **실제 유료 모델 선정 테스트 전에 지켜야 하는 실행 절차**다. 현재 저장본에서는 유료 inference를 실행하지 않았다.

## 1. 확정 정책

- 모델 선정 후보: 정확한 OpenRouter ID **4개**
- 기본 후보 4개:
  - `google/gemini-3.1-flash-lite`
  - `google/gemini-3-flash-preview`
  - `deepseek/deepseek-v3.2`
  - `openai/gpt-5.4-mini`
- 위 ID는 2026-09-24 OpenRouter 공개 모델 페이지 기준으로 확인한 후보이며, **실제 실행 직전 ZDR endpoint catalog에서 다시 검증**한다. Qwen 3.8은 사용자 결정으로 제외한다.
- Qwen 3.8은 사용자 결정으로 현재 선정 후보에서 제외
- 4개 모델 전체 선정 테스트 누적 비용 상한: **$5.00**
- $5는 목표 소비액이 아니라 최대 허용치
- 전체 프로젝트 예산 참고값 `$30`과 모델 선정 테스트 상한 `$5`를 섞지 않음

정확한 후보 슬롯은 `evals/model_candidates.example.json`, 기계 판정 정책은 `evals/model_selection_policy.json`을 정본으로 사용한다.

## 2. ZDR 보안 규칙

1. OpenRouter 전용 테스트 키를 사용하고 key spending limit을 **$5 이하**로 설정한다.
2. 키 값은 `.env`에만 저장하고 코드·명령행 인자·로그·리포트에 출력하지 않는다.
3. 실행 직전 `evals/openrouter_zdr_preflight.py`가 OpenRouter의 `/api/v1/endpoints/zdr`를 조회해 **모델별 실제 ZDR endpoint 존재 여부·provider·가격**을 확인한다.
4. ZDR endpoint라도 설정한 가격 상한(`prompt <= $1/M`, `completion <= $5/M`)을 넘으면 후보를 실행하지 않는다.
5. 서비스 코드는 STRICT, FORMAT FALLBACK, REPAIR를 포함한 모든 OpenRouter 요청에 `provider.zdr=true`, `provider.data_collection="deny"`, `provider.max_price`를 강제한다.
6. ZDR가 불가능하거나 가격 상한을 만족하는 ZDR endpoint가 없으면 유료 inference 전에 실패한다. 다른 model/non-ZDR endpoint로 자동 대체하지 않는다.
7. 실제 고객 개인정보·운영 비밀은 모델 선정 데이터에 사용하지 않는다.
8. ZDR는 OpenRouter/Provider 보존 정책의 경계다. 로컬 결과·Langfuse·키 관리까지 자동 보호하는 것은 아니므로 별도 신뢰 경계를 유지한다.

## 3. Langfuse 선연결

공식 4모델 선정 테스트는 **Langfuse를 먼저 연결한 뒤** 실행한다. 첫 유료 호출부터 동일한 관측 증거를 남기기 위한 고정 규칙이다.

- 공식 runner는 `--allow-observability-export`가 없으면 실행을 거부한다.
- 이 옵션을 켜면 runner가 **유료 inference 전에** 안전한 preflight 이벤트를 전송한다.
- 전송 실패 시 유료 모델 테스트를 시작하지 않는다.
- Langfuse에는 모델/버전/stage/token/cost/latency/Tool 상태/평가 메타데이터만 허용하고 원문 고객 발화, 승인 힌트 본문, 정답, API Key는 보내지 않는다.
- 실제 Langfuse SDK/네트워크 연결 성공은 키를 넣은 환경에서 별도 확인한다.

## 4. 공식 테스트 공정성

4개 모델은 아래 조건을 동일하게 유지한다.

- `evals/dataset.jsonl` 동일 30문항과 SHA-256
- 같은 System Prompt
- 같은 Domain Skill/Policy
- 같은 세션 Context/fixture
- 같은 MCP Tool 계약
- 같은 Pydantic/Policy 출력 계약과 REPAIR 규칙
- `temperature=0`, `max_output_tokens=850`
- 같은 평가 계약 `evals/core30_quality_contract.json`

1차 비교에서 변경하는 것은 **model ID 하나**뿐이다.

## 5. 테스트 게이트

| 게이트 | 통과 기준 |
|---|---|
| Security | 4개 exact model ID, ZDR preflight PASS, request ZDR 강제, non-ZDR fallback 없음 |
| Dataset | core-30 정확히 30건, policy/quality-contract의 SHA가 현재 파일과 일치 |
| Hardcoding | `evals/audit_runtime_hardcoding.py` 위반 0 |
| Completion | 각 모델 30/30 사례 실행 완료 |
| Contract | 최종 JSON/Pydantic/Policy 계약 30/30 |
| Safety | Hard Fail 0 |
| Domain | 현재 core-30 30/30 목표. 사람 검토 필요 사례는 검토 전 PASS로 간주하지 않음 |
| Budget | 4개 모델 합산 actual provider-reported cost ≤ $5.00 |
| Efficiency | 품질 통과 후보끼리 calls/token/cost/p50/p95 비교 |

## 6. 측정할 값

각 사례와 모델 전체에서 아래를 기록한다.

- INITIAL / FOLLOWUP / REPAIR / FORMAT_FALLBACK별 Provider call
- 실제 provider call 총수와 case당 평균
- input/output/total token
- reasoning token, cached/cache-write token: Provider가 보고할 때만
- 실제 provider-reported USD cost 및 완전성 여부
- LLM/Tool/Validation/전체 case latency와 p50/p95
- Tool 선택·실행·Observation 이후 판단 변화
- FOLLOWUP에 context/previous decision/tool result가 다시 포함됐는지
- Prompt 구성별 token **추정치**와 실제 Provider input token을 명확히 분리

MCP Tool 실행과 로컬 Pydantic 검증 자체는 LLM token을 소비하지 않는다. Tool 결과를 FOLLOWUP에서 읽을 때는 LLM input token이 발생한다.

## 7. 실행 전 오프라인 확인

PowerShell:

```powershell
python evals/run_model_comparison.py --offline-only
python evals/audit_runtime_hardcoding.py
```

둘 다 PASS하기 전에는 유료 테스트를 시작하지 않는다.

## 8. 후보 ID와 ZDR/가격 확인

기본 4개 ID는 `evals/model_candidates.example.json`에 이미 들어 있다. `OPENROUTER_MODELS`를 비워두면 그대로 사용한다.

API Key를 `.env`에 넣은 뒤 **추론 없이** ZDR endpoint/가격만 확인할 수 있다.

```powershell
python evals/openrouter_zdr_preflight.py --models "google/gemini-3.1-flash-lite,google/gemini-3-flash-preview,deepseek/deepseek-v3.2,openai/gpt-5.4-mini"
```

이 단계의 `inference_requests`와 `billable_requests`는 0이어야 한다.

## 9. 공식 4모델 실행

`.env`에 OpenRouter/Langfuse 키를 직접 넣은 뒤 사용한다. 키 자체는 명령에 쓰지 않는다.

```powershell
python evals/run_model_selection.py `
  --allow-external-llm `
  --allow-observability-export `
  --confirm-dedicated-key-cap
```

`--confirm-dedicated-key-cap`은 전용 OpenRouter 테스트 키에 `$5 이하` spending limit을 직접 확인했다는 표시다. runner의 소프트웨어 budget guard만으로 계정 수준 하드 상한을 보장하지 않는다.

## 10. 결과 해석

최종 탑재 모델은 자동으로 순위를 매겨 결정하지 않는다.

먼저 ZDR, 30개 완료, Hard Fail 0, 계약 안정성, Domain 판단 품질을 확인한다. 그 조건을 만족한 후보끼리 실제 Provider call 수, token, 비용, p50/p95 지연을 비교한다.

`30/30`은 **현재 core-30 평가셋에서 모두 통과했다는 뜻**이며 실제 서비스 전체 정확도 100%나 99.x%를 입증한다는 뜻이 아니다.
