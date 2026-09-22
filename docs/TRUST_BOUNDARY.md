# Trust Boundary - 2차 프로젝트

> 기준: 2026-09-22.v3. RAG와 LangGraph는 사용하지 않는다.

## 경계 표

| 입력/데이터 | 현재 처리 | 코드 통제 |
|---|---|---|
| 고객 `message` | LLM 구조화 판단 입력 | 사용자 문장을 정책 지시로 신뢰하지 않음 |
| `skills/domain_policy.json` | version이 있는 Domain Skill | 확정 경계/LLM guidance/미확정 정책/visibility 분리 |
| LLM `IntentResult` | Pydantic enum 정규화 | 허용 action/lookup만 사용 |
| `applied_skill_rules` | LLM 자기보고 rule id | 존재하는 ID만 필터링. 실제 준수 여부는 별도 평가 |
| 읽기 MCP 결과 | `tool_results`로 2차 LLM 판단에 전달 | 현재 세션/팀으로 범위 제한 |
| 승인 힌트 | `get_approved_hint`로만 조회 | 자유 힌트 생성 금지 |
| 운영 요청 쓰기 | LLM 최종 action 후 실행 | 세션/팀/idempotency/상태 전이 검증 |
| 정답 | AnswerVault 분리 | 일반 LLM context/응답에서 직접 노출 금지 |
| 문제 번호/전체 문제 수 | 내부 판단 정보 | 고객 안내에 직접 노출 금지 |
| Langfuse | allowlist 메타데이터만 | 힌트/정답/전사 전문/비밀정보/불필요한 고객 원문 제외 |

## 두 단계 도구 경계

1. LLM은 필요한 읽기 조회만 선택한다.
2. 코드는 허용된 lookup만 실행한다.
3. 결과를 LLM이 다시 읽어 후속 행동을 판단한다.
4. 부작용 action은 별도 코드 검증 뒤 실행한다.

읽기 결과 안의 문자열도 system instruction으로 승격하지 않는다.

## 호출 제한

기본 1회 LLM 판단을 사용하고, 읽기 lookup이 필요한 경우에만 1회의 후속 판단을 허용한다. 두 번째 판단이 다시 lookup을 요구해도 반복 루프를 만들지 않는다.

## 관측 경계

초기 LLM, lookup, 후속 LLM, 실제 처리, 최종 결과는 같은 request/session 식별자로 연결한다. 비용 미제공은 0으로 바꾸지 않는다. 코드의 버전 문자열 기록과 외부 Prompt Management/교체/롤백 검증은 별개 상태로 기록한다.

## 아직 미검증

- 실제 원격 MCP의 악의적 반환값에 대한 통합 공격 테스트
- 실제 OpenRouter 모델별 prompt injection/회귀 평가
- 운영자 인증/권한 체계
- Langfuse 외부 Dataset/Prompt 교체·롤백
