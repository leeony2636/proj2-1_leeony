# Spec — 고객 힌트 요청 Agent

## Why

- **페르소나**: 방탈출 진행 중 힌트가 필요한 고객
- **상황**: 고객이 현재 퍼즐을 선택하고 자연어로 힌트 또는 직원 도움을 요청
- **문제**:
  1. 같은 "힌트 주세요"라도 현재 시간·진도·재요청 여부가 다름
  2. 장비 이상을 일반 힌트로 처리하면 잘못된 대응이 됨
  3. 테마마다 전체 퍼즐 수가 달라 절대 문제 수 기준만 쓰기 어려움
- **측정 지표**: 의도/Tool 선택, 스키마 준수, p50/p95 지연, 요청당 비용

## Goal

- 단일 `POST /api/agent`에서 요청을 구조화해 처리한다.
- 장비 이상/직원 호출은 `MASTER_REQUEST`로 분기한다.
- 정보 부족은 `NEED_MORE_INFO`로 반환한다.
- 일반 힌트는 MCP 조회 후 코드 판정 엔진을 거친다.
- 구조화 출력 계약은 최종적으로 100회 이상 테스트할 계획이다.
- **Out of Scope**: 선제 힌트, RAG/LangGraph, 실제 ERCC 직접 제어

## What

**Happy Path**
1. 고객이 `session_id`, `team_id`, `puzzle_id`, `message` 전송
2. LLM이 의도/감정/추가정보 필요 여부 구조화
3. Agent가 MCP로 세션/퍼즐/힌트 이력 조회
4. 코드가 힌트 강도 결정
5. MCP가 승인 HintStep 조회
6. `PROVIDE_HINT` 응답
7. HintEvent/Langfuse 기록

**Edge Cases**

| # | 상황 | 처리 |
|---|---|---|
| EC-01 | `puzzle_id` 없음 | `NEED_MORE_INFO` |
| EC-02 | 장비 고장 표현 | `MASTER_REQUEST` |
| EC-03 | 직원 직접 호출 | `MASTER_REQUEST` |
| EC-04 | 세션 종료 | `CLOSED` |
| EC-05 | 승인 힌트 없음 | `ERROR` 또는 관리자 확인 경로 — 최종 정책 확정 필요 |

## How

```text
POST /api/agent

request:
{
  "session_id": string,
  "team_id": string,
  "puzzle_id": string | null,
  "user_id": string | null,
  "message": string
}

response:
{
  "status": "NEED_MORE_INFO" | "PROVIDE_HINT" | "MASTER_REQUEST" | "CLOSED" | "ERROR",
  "hint_strength": "WEAK" | "NORMAL" | "STRONG" | null,
  "hint_text": string | null,
  "reason_codes": [string]
}
```

## AC

**AC-01 · 장비 이상**
- GIVEN: 유효한 세션에서 고객이 장비 이상을 입력
- WHEN: `/api/agent` 호출
- THEN: 일반 힌트가 아니라 `MASTER_REQUEST` 반환

**AC-02 · 정보 부족**
- GIVEN: 힌트 요청인데 `puzzle_id` 없음
- WHEN: `/api/agent` 호출
- THEN: `NEED_MORE_INFO` 반환

**AC-03 · 강한 힌트 기본 규칙**
- GIVEN: 남은 시간 15분 이하, 남은 문제 비율 50% 이상
- WHEN: 일반 힌트 판정
- THEN: `STRONG` 후보와 `TIME_PROGRESS_STRONG_RULE` reason code
