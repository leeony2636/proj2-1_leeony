# Spec — 고객 힌트 요청 Agent

## Why

- **페르소나**: 방탈출 진행 중 힌트가 필요한 고객
- **상황**: 고객이 현재 퍼즐을 선택하고 텍스트 또는 음성으로 힌트·직원 도움을 요청
- **문제**:
  1. 같은 "힌트 주세요"라도 현재 시간·진도·재요청 여부가 다름
  2. 장비 이상을 일반 힌트로 처리하면 잘못된 대응이 됨
  3. 테마마다 전체 퍼즐 수가 달라 절대 문제 수 기준만 쓰기 어려움
- **측정 지표**: 의도/Tool 선택, 스키마 준수, p50/p95 지연, 요청당 비용

## Goal

- 단일 `POST /api/agent`에서 요청을 구조화해 처리한다.
- 음성 입력은 STT Adapter가 전사한 텍스트를 기존 `message` 필드로 전달한다.
- 장비 이상/직원 호출은 `MASTER_REQUEST`로 분기한다.
- 정보 부족은 `NEED_MORE_INFO`로 반환한다.
- 일반 힌트는 MCP 조회 후 코드 판정 엔진을 거친다.
- 구조화 출력 계약은 최종적으로 100회 이상 테스트할 계획이다.
- **Out of Scope**: 선제 힌트, RAG/LangGraph, 실제 ERCC 직접 제어

### 수정 기획안과 현재 계약의 미정 항목

수정 기획안에는 고객 요청을 `힌트 / 장비 이상 / 게임마스터 호출 / 일반 문의`로 분류한다고 적혀 있다. 현재 실행 schema에는 `GENERAL_INQUIRY`가 없고 일반 문의의 응답 상태·허용 데이터·평가 정답이 정의되어 있지 않다. 따라서 이번 정렬에서는 새 enum이나 분기를 임의로 추가하지 않는다.

또한 수정 기획안은 승인 결과를 LLM이 사용자 친화적인 문장으로 표현하는 목표를 포함하지만, 현재 구현은 승인 힌트 원문과 코드 상태를 직접 응답한다. 별도 응답 생성 단계의 입력/출력 계약과 실패 정책이 확정되기 전에는 두 번째 LLM 호출을 추가하지 않는다.

## What

**Happy Path**
1. 고객이 텍스트를 입력하거나 음성 요청을 제출
2. 음성인 경우 STT Adapter가 전사·신뢰도를 확인하고 `message`를 만든다.
3. 고객 클라이언트가 `session_id`, `team_id`, `puzzle_id`, `message`를 전송한다.
4. LLM이 의도/감정/추가정보 필요 여부를 구조화한다.
5. Agent가 MCP로 세션/퍼즐/힌트 이력을 조회한다.
6. 코드가 힌트 강도를 결정한다.
7. MCP가 결정된 승인 HintStep을 조회한다.
8. `PROVIDE_HINT` 응답으로 WEAK 또는 STRONG 힌트를 자동 제공한다.
9. HintEvent/Langfuse 기록

**ANSWER Path**
1. 고객이 정답을 직접 요청하면 STRONG 힌트를 먼저 자동 제공한다.
2. Agent는 정답 문자열 대신 일회성 `offer_id`와 `ANSWER_CONFIRMATION_REQUIRED`를 반환한다. 현재 코드의 `_OFFER_TTL`은 10분이며, 최종 유효시간은 팀 확정이 필요하다.
3. 고객이 `POST /api/answers/confirm`으로 동의하면 AnswerVault가 토큰을 소비하고 정답을 반환한다.
4. 토큰 재사용·만료·세션/문제 불일치는 거부한다.

**Edge Cases**

| # | 상황 | 처리 |
|---|---|---|
| EC-01 | `puzzle_id` 없음 | `NEED_MORE_INFO` |
| EC-02 | 장비 고장 표현 | `MASTER_REQUEST` |
| EC-03 | 직원 직접 호출 | `MASTER_REQUEST` |
| EC-04 | 세션 종료 | `CLOSED` |
| EC-05 | 승인 힌트 데이터 없음 | `MASTER_REQUEST`로 운영 확인 요청 |
| EC-05-1 | 승인 힌트 조회의 일시적 timeout/connection 실패 | 1회 재시도 후 `ERROR`, 임의 대체 힌트 생성 금지 |
| EC-06 | 정답 직접 요청 | STRONG 자동 제공 후 `ANSWER_CONFIRMATION_REQUIRED` |
| EC-07 | 정답 동의 토큰 오류/만료 | `403`, 정답 미공개 |
| EC-08 | STT 실패·빈 전사·낮은 신뢰도 | LLM/MCP 호출 없이 재입력 요청 |

## How

```text
POST /api/agent

request:
{
  "request_id": string,
  "session_id": string,
  "team_id": string,
  "puzzle_id": string | null,
  "user_id": string | null,
  "message": string
}

response:
{
  "status": "NEED_MORE_INFO" | "PROVIDE_HINT" | "ANSWER_CONFIRMATION_REQUIRED" | "MASTER_REQUEST" | "CLOSED" | "ERROR",
  "hint_strength": "WEAK" | "NORMAL" | "STRONG" | null,
  "hint_text": string | null,
  "reason_codes": [string]
}

POST /api/answers/confirm

request:
{
  "session_id": string,
  "team_id": string,
  "puzzle_id": string,
  "offer_id": string
}

response:
{
  "puzzle_id": string,
  "answer": string,
  "policy": "USER_EXPLICIT_CONFIRMATION"
}
```

STT 내부 결과는 다음처럼 정규화하지만 P0의 `/api/agent` 외부 계약에는 음성 원문을 포함하지 않는다.

```json
{
  "transcript": "이 퍼즐 힌트 주세요",
  "confidence": 0.0,
  "language": "ko-KR",
  "duration_ms": 0
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

**AC-04 · STRONG 자동 제공**
- GIVEN: 코드가 시간·진도·반복 요청 기준으로 STRONG을 결정함
- WHEN: `/api/agent` 호출
- THEN: 고객 동의 없이 승인된 STRONG 힌트를 `PROVIDE_HINT`로 반환하고 이력을 기록함

**AC-05 · ANSWER 동의 흐름**
- GIVEN: STRONG 힌트가 실제 제공된 세션에서 고객이 정답을 직접 요청함
- WHEN: `/api/agent` 호출
- THEN: STRONG 힌트와 `ANSWER_CONFIRMATION_REQUIRED`, 일회성 `offer_id`를 반환하고 정답은 포함하지 않음

**AC-06 · ANSWER 확인**
- GIVEN: 유효한 `offer_id`와 동일 세션·문제
- WHEN: `/api/answers/confirm` 호출
- THEN: 토큰을 소비하고 `USER_EXPLICIT_CONFIRMATION` 정책으로 정답을 한 번 반환함

**AC-07 · ANSWER 자동 제공 보류**
- GIVEN: 남은 시간 5분 이하이고 잔여 퍼즐이 2개 이상임
- WHEN: 자동 제공 정책 판정
- THEN: MVP feature flag가 비활성이라 항상 고객 동의 흐름을 유지함

**AC-08 · STT 실패 경계**
- GIVEN: 음성 전사가 실패하거나 신뢰도가 기준 미만임
- WHEN: 고객이 음성 힌트 요청을 제출함
- THEN: LLM/MCP를 호출하지 않고 다시 말하기 안내를 반환함
