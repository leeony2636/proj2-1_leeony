# Architecture

## 현재 처리 흐름

```text
Customer UI
   ↓
FastAPI /api/agent
   ↓
Code Guard 1
(session/team/current puzzle/spoiler/session closed)
   ↓
Context Builder
(minimum session context + recent turns + Domain Skill v2026-09-22.v3)
   ↓
LLM INITIAL decision
(intent(s) + lookup_tools + clarification + actions + support_need + self-reported skill rule ids)
   │
   ├─ 조회 불필요 → 바로 Code Guard 2
   │
   └─ 조회 필요 → read-only MCP lookup
                  (hint history / current session master-request status)
                        ↓
                  LLM FOLLOWUP_AFTER_TOOLS
                  (tool result를 보고 최종 action/question 결정)
                        ↓
Code Guard 2
(allowed action / approved hint / AnswerVault / idempotency / state transition)
   ↓
Side-effect MCP tools
   ↓
Verified execution result + AgentResponse + conversation history
```

## LLM이 실제로 결정하는 것

- 표현과 최근 대화를 이용한 요청 의미·복합성
- 필요한 정보가 DB/MCP 조회인지 고객 확인 질문인지
- `get_hint_history`, `get_master_request_status` 중 필요한 읽기 조회
- 조회 결과를 본 뒤 힌트/직원 요청/장비 요청/질문/정보 안내 중 후속 대응
- `STANDARD/STRONG/ANSWER` 지원 필요도
- 직원 전달용 `facts / attempts / unknowns`
- 자신의 판단에 사용했다고 보고하는 Domain Skill rule id

`applied_skill_rules`는 LLM 자기보고 값이다. 존재하는 rule id인지 필터링할 수는 있지만, 실제 규칙을 올바르게 적용했는지는 평가에서 별도로 판정한다.

## 코드가 결정하거나 강제하는 것

- 세션·팀·테마·현재 퍼즐 경계
- LLM 출력 스키마와 허용 action/lookup
- 승인된 `WEAK/STRONG` 힌트만 조회하는 콘텐츠 경계
- 정답 AnswerVault/동의 경계
- 시간 연장 자동 적용 금지, 고객 진도 직접 변경 금지
- idempotency, 운영 요청 상태 전이, 조회/승인 힌트 재시도 제한
- 실제 도구 실행 성공 여부와 최종 응답의 구조적 일치

`support_need`의 도메인상 적절성은 코드가 재판정하지 않는다. `hint_policy.py`는 LLM 판단을 승인된 힌트 데이터 단계로 매핑할 뿐이며, 의미 품질은 사람이 정한 Domain Skill/평가셋으로 검증한다.

## Domain Skill 적용 경계

- `skills/SKILL.md`: 현장 경험/과거 기준 원문
- `skills/domain_policy.json`: 실제 LLM 입력용 compact policy
- 현재 적용 버전: `2026-09-22.v3`
- 위치 혼동은 즉시 강한 지원으로 확대하지 않는 참고 기준을 사용
- 문제 번호/전체 문제 수는 내부 정보로 유지하고 고객 안내에 직접 노출하지 않음
- 숫자 기반 힌트 강도 규칙과 재요청 자동 STRONG은 미확정으로 유지

## 고정 조회를 줄인 이유

세션·현재 퍼즐·최근 대화는 최소 맥락으로 항상 제공한다. 반면 힌트 이력이나 기존 직원 요청 상태는 모든 질문에 필요하지 않으므로 LLM이 `lookup_tools`로 선택했을 때만 조회한다. 조회가 발생하면 최대 한 번의 후속 LLM 판단을 수행해 반복 루프를 만들지 않는다.

## 요청 단위 관측

초기 LLM 판단, 조회 도구, 후속 LLM 판단, 승인 힌트/운영 요청 처리, 최종 응답은 같은 `request_id`와 `session_id`로 연결한다. LLM 호출에는 Prompt/Skill 버전, 모델, stage, latency, token, provider가 제공한 cost를 기록한다. 비용이 미제공이면 `None/NOT_PROVIDED`로 유지하며 0으로 바꾸지 않는다.

## 대표 분기

- `아까 직원 불렀는데 아직 안 왔어요.` → 직원 요청 상태 조회 → 결과를 본 뒤 중복 접수/안내를 다시 판단
- `아까 힌트대로 했는데 안 열려요.` → 같은 퍼즐 힌트 이력 조회 → 풀이 어려움/사용법/장비 가능성을 구분하기 위한 질문 또는 후속 행동 판단
- `힌트도 필요하고 자물쇠가 반응하지 않아요.` → 독립 요청인지 동일 문제의 다른 해석인지 불명확하면 실행 전에 질문 가능
