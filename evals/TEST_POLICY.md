# Core-30 모델 선정 테스트 정책

이 문서는 **모델을 실행하기 전에 고정하는 평가 계약**이다. 실제 모델 결과를 본 뒤 유리하게 기준을 바꾸지 않는다.

실행/검토 절차는 `docs/EVALUATION.md`의 “팀이 채울 최소 항목과 실행 순서”를 따른다. `quality_contract_approval.json`의 독립 검토 승인 전에는 공식 유료 평가를 시작하지 않는다. 사람 의미 평가 6축은 코드가 임의 합격시키지 않으며, 구조화 출력과 비용은 별도 자동 측정한다.

## 1. 목적

OpenRouter 유료 후보 **4개**를 동일 조건으로 비교해 방탈출 운영 보조 Agent에 적합한 최종 탑재 후보를 찾는다.
모델 이름의 일반적 평판보다 이 프로젝트의 Prompt · Domain Skill/Policy · Context · MCP Observation을 얼마나 정확하게 이해하고 적용하는지를 본다.

## 2. 고정 조건

- 평가셋: `evals/dataset.jsonl` 30건
- 정본 SHA-256: `model_selection_policy.json`의 `dataset_sha256`과 일치해야 함
- Prompt/Skill/Context/MCP/출력 계약은 4개 모델에 동일하게 적용
- 1차 비교에서 바꾸는 값은 **정확한 OpenRouter model ID**뿐
- `temperature=0`, `max_output_tokens=850`
- Qwen 3.8은 현재 후보에서 제외
- 이름/버전을 모르는 모델 ID는 추측해서 채우지 않음

## 3. 보안 게이트 — 유료 호출 전 전부 PASS

1. `OPENROUTER_API_KEY` 존재 여부만 확인하고 값은 출력하지 않음
2. 정확한 model ID 4개가 준비되어야 함
3. 4개 모두 실행 직전 ZDR filtered catalog에서 확인
4. 모든 OpenRouter 요청에 `provider.zdr=true`, `provider.data_collection="deny"` 강제
5. 비-ZDR endpoint 또는 다른 모델로 자동 fallback 금지
6. 모델 선정용 전용 key spending limit이 **$5 이하**임을 사용자가 확인
7. **공식 4모델 선정 테스트는 Langfuse를 먼저 연결**하고, 유료 inference 전에 안전한 preflight event 전송 성공 필요
8. Langfuse에는 원문 고객 발화·힌트/정답 본문·API Key를 보내지 않음
9. Langfuse 없이 하는 실행은 개발 진단용으로만 보고 공식 모델 선정 결과로 사용하지 않음

하나라도 만족하지 않으면 **Provider inference 0회**로 중단한다.

## 4. 비용 게이트

- 4개 모델 전체 선정 테스트의 누적 상한: **$5.00**
- $5는 소진 목표가 아니라 최대 허용치다. $1~2에서 비교가 완료되면 그대로 종료한다.
- 각 모델당 $5가 아니다.
- Provider가 실제 비용을 보고하지 않으면 다음 모델/다음 사례로 계속 진행하지 않는다.
- 소프트웨어 중단은 사례 경계에서만 가능하므로 최종 하드 상한은 OpenRouter 전용 key limit으로 보완한다.

## 5. 품질 게이트

최종 목표는 현재 core-30에서 다음 조건을 충족하는 것이다.

- 완료 사례: 30/30
- Domain 품질: 30/30 목표
- Hard Fail: 0건
- 최종 출력 계약: 30/30
- 필요한 Tool 선택 및 Observation 이후 판단이 기대 흐름과 일치
- 판단·실행·최종 안내가 모순되지 않음

`PARTIAL`이나 `REVIEW_REQUIRED`는 분석에는 사용할 수 있지만 **30/30 PASS로 계산하지 않는다**. 의미 판정이 사람 검토가 필요한 사례는 검토 완료 전 최종 30/30으로 보고하지 않는다.

## 6. 하드코딩 금지

Agent Runtime/Prompt에는 다음을 넣지 않는다.

- case ID별 정답 분기
- 평가 발화 원문과 정답의 literal 매핑
- `expected`, `service_expected`, reviewer 판정, quality contract
- 특정 평가 문제를 맞히기 위해 추가한 문장별 규칙

허용되는 것은 여러 실제 상황에 일반화되는 Domain Policy/Skill 규칙과 안전·권한 계약이다.
`evals/audit_runtime_hardcoding.py`가 Runtime과 Evaluator 경계를 점검한다.

## 7. 모델이 실제로 판단하는지 확인하는 항목

각 사례에서 다음을 별도로 본다.

- 사용자 의도와 복합 요청 이해
- Domain Skill/Policy 적용
- 세션/최근 대화/현재 상태 Context 활용
- 필요한 조회 Tool 선택 및 불필요 Tool 억제
- MCP Observation 해석
- INITIAL → FOLLOWUP 판단의 적절한 유지/변경
- 추가 질문의 필요성
- support_need 및 action 결정
- 실행 결과와 고객 안내의 일치

## 8. 계측 기준

Provider가 반환한 값과 추정치를 섞어 표시하지 않는다.

### 실제 Provider 값

- provider call count
- input / output / total tokens
- reasoning tokens: Provider가 제공할 때만 기록
- cached/cache-write tokens: Provider가 제공할 때만 기록
- 실제 비용 USD: Provider가 제공할 때만 기록
- 각 LLM call latency

### 로컬 측정

- Tool call count / latency
- Tool 실행 자체의 LLM token 사용량 = 0
- JSON/Pydantic/Policy validation latency; LLM token 사용량 = 0
- 전체 case latency, p50/p95
- REPAIR / format fallback 횟수

### Prompt 구성별 토큰

Provider는 System/Skill/Context/Tool result별 token을 직접 분리해 주지 않으므로, 구성별 수치는 **추정치**로만 기록한다.
실제 Provider input token을 기준으로 문자 길이에 비례한 추정임을 결과에 명시한다.

구성 항목: System Prompt, user message, base context, Domain Skill, recent turns, Tool result, previous decision, instruction, REPAIR payload.

## 9. 상태 기억 검증

Provider 호출은 기본적으로 독립 요청이다. FOLLOWUP에서는 이전 호출을 자동 기억한다고 가정하지 않는다.
테스트는 다음이 다시 전달되었는지 기록한다.

- current context
- previous decision
- Tool results

이 값이 필요한 FOLLOWUP에서 빠졌으면 품질 결과와 별개로 파이프라인 결함으로 기록한다.

## 10. 선정 순서

1. ZDR/보안 게이트
2. core-30 완료 여부
3. Hard Fail 0
4. 출력 계약 안정성
5. Domain 판단 품질
6. 위 조건을 만족한 후보 사이에서 Provider call 수 → token → 비용 → p50/p95 지연 비교

가장 싼 모델이나 가장 큰 모델을 자동 선정하지 않는다. 최종 탑재 모델 선택은 이 결과를 근거로 팀이 결정한다.
