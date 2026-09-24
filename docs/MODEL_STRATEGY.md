# LLM 모델 선정 전략 — 현재 기준

## 목적

우리 Agent는 Prompt + Domain Skill/Policy + Session Context + 필요 시 MCP Observation을 LLM에 제공한다.
모델 선정은 일반적인 모델 순위가 아니라 **이 정보를 읽고 상황에 맞게 판단하는 능력**을 같은 조건에서 비교하는 작업이다.

## 현재 LLM 역할

LLM이 판단한다.

- 사용자 의도와 복합 요청
- 정보 부족 여부와 추가 질문
- 필요한 read-only MCP Tool
- Tool 결과를 받은 뒤 FOLLOWUP 판단
- `support_need` (STANDARD / STRONG / ANSWER)
- 실행할 action과 짧은 판단 근거

코드/MCP는 의미 판단을 다시 하지 않고 안전 경계를 강제한다.

- 세션·팀·현재 퍼즐 권한
- 승인된 WEAK/STRONG 힌트만 조회·반환
- ANSWER 별도 동의/AnswerVault
- 직원 요청 상태와 멱등성
- strict 출력 계약과 오류 처리

## 4모델 비교 원칙

정본은 `evals/TEST_POLICY.md`와 `evals/model_selection_policy.json`이다.

- OpenRouter 유료 후보 4개
- Qwen 3.8은 현재 후보에서 제외
- exact model ID를 확인한 모델만 사용
- 4개 모델 전체 선정 테스트 최대 `$5`
- ZDR + `data_collection=deny` 필수
- Prompt/Skill/Context/MCP/계약/temperature/max output은 동일
- 1차 비교에서는 model ID만 변경

## 품질 우선순위

1. ZDR/보안 통과
2. 현재 core-30 완료
3. Hard Fail 0
4. 출력 계약 안정성
5. Domain 판단 30/30 목표
6. 위 조건을 만족한 후보 사이에서 calls/token/cost/p50/p95 비교

정답·case ID를 Runtime/Prompt에 하드코딩해서 점수를 맞추지 않는다.
