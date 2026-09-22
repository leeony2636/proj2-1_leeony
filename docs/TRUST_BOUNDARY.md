# Trust Boundary — 2차 프로젝트

> 기준: 2026-09-22. RAG와 LangGraph는 사용하지 않는다.

## 목적

사용자 입력, STT 전사, 외부 Provider 응답, MCP/외부 도구 반환값을 시스템 지시나 확정 사실처럼 신뢰하지 않는다. 2차 프로젝트 가이드의 신뢰 경계 요구를 현재 코드에 대입한 기록이다.

## 경계 표

| 입력/데이터 | 현재 처리 | 신뢰 여부 | 남은 확인 |
|---|---|---|---|
| 고객 `message` | `IntentResult`로 구조화 후 코드 정책 적용 | 신뢰하지 않음 | 인젝션 평가 3건 이상 미확정 |
| STT `transcript` | confidence/빈 전사 경계 후 기존 text Agent로 전달 | 신뢰하지 않음 | 최종 Large Epoch2 실제 통합 Gate 2 미완료 |
| LLM `IntentResult` | Pydantic 정규화, Tool allowlist | 최종 판정으로 신뢰하지 않음 | Langfuse Prompt version 연동 미완료 |
| MCP 세션/퍼즐/힌트 반환값 | Pydantic/세션·팀·현재 퍼즐 검증 뒤 사용 | 무검증 신뢰 금지 | 원격 `/mcp` transport 미검증 |
| 승인 힌트 | `get_approved_hint`로만 조회, 실패 시 임의 생성 금지 | 승인 데이터만 허용 | 데이터 출처 담당자/라이선스 기록 보강 필요 |
| Master Request 쓰기 | 세션·팀 검사, idempotency, 상태 전이 제한 | 명시적 정책 통과 후만 허용 | 운영자 인증은 미구현 |
| 정답 데이터 | `AnswerVault` 분리, `offer_id` 확인 후만 공개 | 일반 LLM/MCP 응답에서 금지 | offer TTL 최종값 팀 결정 필요 |

## 시스템 지시와 외부 내용 분리

현재 LLM system prompt는 코드에 고정되어 있고 사용자 payload는 별도 `user` 메시지 JSON으로 전달한다. MCP 도구 이름은 코드 allowlist를 사용한다. 외부 도구 반환 텍스트를 system instruction으로 재해석하거나 다른 도구의 지시로 전달하는 기능은 구현하지 않는다.

## 부작용 도구

현재 고객 Agent가 사용할 수 있는 쓰기 동작은 힌트 이력 기록과 게임마스터 요청 생성/상태 변경이다. `mark_puzzle_solved`는 Runtime 내부 기능으로만 남기고 FastMCP 공개 도구 및 고객 HTTP route에서는 제외한다. 추가 자동화 권한은 만들지 않는다.

## 아직 통과하지 못한 검증

- 평가셋에 명시적인 prompt/tool injection 케이스 3건 이상을 확정하지 못했다.
- 원격 MCP 반환값이 악의적 문자열을 포함하는 통합 테스트는 없다.
- 운영자 인증/권한 체계는 실제 배포 기준으로 검증되지 않았다.
- "통과"를 안전 보장으로 표현하지 않고, 시도한 공격과 남은 한계를 EVAL_REPORT에 기록해야 한다.
