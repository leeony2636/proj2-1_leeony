# LLM Provider 개발 가이드 — 현재 기준

## 현재 운영 경계

LLM 호출은 `backend/services/llm.py` 한 곳에 모은다.
공식 모델 선정은 `LLM_PROVIDER=openrouter`만 사용하며 `baseline`은 오프라인 구조 smoke/비교 전용이다. OpenRouter 실패를 baseline이나 다른 모델로 자동 대체하지 않는다.

## OpenRouter 보안

- exact `OPENROUTER_MODEL` 필수
- 모든 요청에 `provider.zdr=true`
- 모든 요청에 `provider.data_collection="deny"`
- 실행 전 ZDR filtered catalog preflight
- 비-ZDR/model fallback 금지
- API Key 값은 로그/결과에 남기지 않음

## 모델 비교

4개 후보에 같은 core-30, Prompt, Skill, Context, MCP, 계약, temperature, max output을 적용하고 model ID만 바꾼다.
모델 선정 전체 테스트 비용 상한은 `$5`이며 각 모델당 `$5`가 아니다.

평가 우선순위는 Domain 판단/Hard Fail/계약 안정성이고, 이를 만족한 후보 사이에서 Provider call 수, token, 실제 비용, p50/p95 지연을 비교한다.

자세한 실행 계약은 `evals/TEST_POLICY.md`와 `docs/OPENROUTER_ZDR_BUDGET_RUNBOOK.md`를 따른다.
