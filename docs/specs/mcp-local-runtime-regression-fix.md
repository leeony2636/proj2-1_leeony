# MCP LocalRuntime 저장·진도 회귀 수정

## Why

- **페르소나**: 방탈출 진행 중 힌트를 요청하는 참가자와 진행 상태를 관리하는 게임마스터
- **상황**: 현재 P0 MCP adapter는 같은 프로세스에서 `LocalRuntime`을 호출해 세션과 힌트 이력을 저장한다.
- **문제**:
  1. `record_hint_delivery`가 제거된 전역 변수 `_LOCK`, `_HINT_EVENTS`를 참조해 힌트 제공 시 `NameError`가 발생한다.
  2. `mark_puzzle_solved`가 지역 변수 `s`를 만든 뒤 정의되지 않은 `session`을 사용해 다음 문제 갱신 시 `NameError`가 발생한다.
  3. 두 오류 때문에 이미 도입된 Repository 멱등성 계약과 진행 상태 저장이 실제 MCP 흐름에서 동작하지 않는다.
- **측정 지표**: 관련 회귀 테스트 통과율 100%, 동일 멱등성 키의 중복 힌트 이벤트 생성률 0%, 문제 완료 후 세션 저장 성공률 100%

## Goal

- `record_hint_delivery`가 `RuntimeRepository`를 통해 힌트 이벤트와 멱등성 결과를 저장하도록 복원한다.
- `mark_puzzle_solved`가 하나의 `session` 객체만 사용해 현재 문제·완료 상태를 갱신하고 Repository에 저장하도록 복원한다.
- **성공 기준**: `test_idempotency_local_runtime.py`, `test_repository_contract.py`, `test_local_runtime_progression.py`가 모두 통과한다. 전체 회귀 테스트의 기존 정책 충돌은 별도 PR에서 다룬다.
- **Out of Scope**: FastMCP 네트워크 transport 도입, MCP 도구 스키마 전면 개편, PostgreSQL 실제 연결, 힌트 강도 정책 변경, 도메인 데이터 보강

## What

**Happy Path**

1. 승인 힌트 제공 후 `HintEvent`를 Repository에 한 번 저장한다.
2. 동일한 `idempotency_key`와 동일 payload가 재전송되면 기존 결과를 반환하고 이벤트를 추가하지 않는다.
3. 현재 문제를 완료하면 해결 목록과 해결 개수를 갱신하고 다음 미해결 문제를 현재 문제로 지정한다.
4. 마지막 문제까지 완료하면 세션을 종료하고 현재 문제를 `None`으로 저장한다.

**Edge Cases**

| # | 상황 | 처리 방식 |
|---|---|---|
| EC-01 | 동일 멱등성 키·동일 payload 재전송 | 기존 결과 반환, `deduplicated=true`, 이벤트 추가 금지 |
| EC-02 | 동일 멱등성 키·다른 payload 재전송 | `IDEMPOTENCY_CONFLICT` 오류, 상태 변경 금지 |
| EC-03 | 존재하지 않는 문제 완료 요청 | `PUZZLE_NOT_FOUND` 오류, 세션 변경 금지 |
| EC-04 | 이미 해결한 문제 재요청 | 해결 목록 중복 추가 금지 |
| EC-05 | 마지막 문제 완료 | `is_closed=true`, `current_puzzle_id=None` 저장 |

## How

- `record_hint_delivery`
  - `HintEvent.model_dump(mode="json")` 결과를 멱등성 비교 payload로 사용한다.
  - `RuntimeRepository.get_idempotency`, `append_hint_event`, `save_idempotency`만 사용한다.
  - 과거 전역 메모리 변수는 다시 도입하지 않는다.
- `mark_puzzle_solved`
  - `get_game_session`으로 얻은 `session`을 단일 상태 객체로 사용한다.
  - 테마 카탈로그의 문제 ID를 검증한 뒤 해결 목록·현재 문제·종료 상태를 계산한다.
  - 변경된 상태는 `RuntimeRepository.save_session`으로 저장한다.
- 정책·멱등성·상태 전이의 이유는 한국어 주석으로 남긴다.

## AC (Given-When-Then)

**AC-01 · 힌트 이벤트 최초 저장**

- GIVEN: 활성 세션과 아직 사용하지 않은 멱등성 키가 있다.
- WHEN: 승인 힌트 제공 이벤트를 기록한다.
- THEN: 이벤트가 정확히 한 건 저장되고 `deduplicated=false`를 반환한다.

**AC-02 · 동일 요청 중복 차단**

- GIVEN: 같은 멱등성 키와 payload의 이벤트가 이미 저장되어 있다.
- WHEN: 같은 이벤트를 다시 기록한다.
- THEN: 이벤트 수는 증가하지 않고 `deduplicated=true`를 반환한다.

**AC-03 · 멱등성 충돌 차단**

- GIVEN: 같은 멱등성 키로 WEAK 이벤트가 저장되어 있다.
- WHEN: 같은 키로 STRONG 이벤트를 기록한다.
- THEN: `IDEMPOTENCY_CONFLICT`를 발생시키고 기존 이력을 보존한다.

**AC-04 · 다음 문제 진행**

- GIVEN: 마지막 문제가 아닌 현재 문제를 해결했다.
- WHEN: 문제 완료를 기록한다.
- THEN: 해결 목록과 개수가 갱신되고 다음 미해결 문제가 현재 문제로 저장된다.

**AC-05 · 세션 종료**

- GIVEN: 마지막 남은 문제만 미해결 상태이다.
- WHEN: 해당 문제 완료를 기록한다.
- THEN: 세션은 종료되고 현재 문제는 `None`이며 Repository에서 같은 상태를 다시 조회할 수 있다.
