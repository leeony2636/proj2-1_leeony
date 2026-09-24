# Domain Source Registry

> 기준: Domain Skill `2026-09-22.v3`. 확인 가능한 저장소 내용만 기록한다.

| 자산 | 용도 | 실제 LLM 입력 | 상태 |
|---|---|---|---|
| `skills/SKILL.md` | 현장 경험과 과거 판단 기준 원문 | 직접 전체 주입하지 않음 | 원본 참고 기록 |
| `skills/domain_policy.json` | 현재 적용 compact Domain Skill | version/confirmed_boundaries/llm_guidance/visibility | 현재 적용 |
| `backend/data/themes/*.json` | LocalRuntime 시연 테마 | 현재 퍼즐 구조화 context | 합성/시연, 현장 Ground Truth 아님 |
| `backend/data/hints/*.json` | 승인 힌트 조회 계약 | LLM이 직접 본문 생성하지 않음 | 승인자/실매장 출처 보강 필요 |
| `backend/data/answers/*.json` | AnswerVault 시연 정답 | 일반 LLM context에 전달하지 않음 | 승인자/실매장 출처 보강 필요 |
| `evals/dataset.jsonl` | 기존 30건 합성 seed | 흐름 smoke/기술 실험 참고 | 사람 Ground Truth로 사용 금지 |

## SKILL.md 대조 결과

현재 compact policy에 반영된 추가 항목:

- `POSITION_CONFUSION_SUPPORT`: 단순 위치 혼동은 감정 표현만으로 강한 지원으로 확대하지 않고 위치 안내 수준을 우선 고려
- `PUZZLE_POSITION_METADATA_PRIVATE`: 문제 번호/순서와 전체 문제 수는 내부 정보로 유지하고 고객에게 직접 노출하지 않음

현재 미확정으로 유지한 항목:

- `NUMERIC_HINT_STRENGTH_RULE`: 15분/50% 같은 숫자 기준
- `AUTO_REREQUEST_ESCALATION`: 짧은 시간 내 동일 문제 재요청 자동 STRONG

## visibility

`domain_policy.json`의 각 적용 규칙은 고객 노출 가능성을 구분한다.

- `INTERNAL_ONLY`: 내부 판단에만 사용
- `CUSTOMER_SAFE_BEHAVIOR`: 정책명/내부 값은 숨기고 경계에 맞는 안내만 가능
- `CUSTOMER_VISIBLE_AFTER_CODE_APPROVAL`: 코드가 승인한 콘텐츠만 고객에게 전달

## 적용 원칙

- RAG를 사용하지 않는다. Domain Skill은 고정 버전 자산으로 관리한다.
- 구조화된 현재 상태는 MCP/API/Repository를 통해 필요한 때만 조회한다.
- `unconfirmed_policies`는 팀 승인 전 실행 규칙이 아니다.
- `applied_skill_rules`는 LLM 자기보고이며 실제 규칙 준수는 사람/평가 기준으로 별도 판정한다.
- 합성 데이터와 LLM이 만든 데이터는 사람 도메인 정답의 근거로 사용하지 않는다.

