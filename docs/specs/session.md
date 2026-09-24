# Spec — 게임 세션 생성 및 조회

## Why

- **페르소나**: 게임마스터와 임시 입장 방식으로 연결되는 고객
- **상황**: 한 팀의 진행 상태를 `session_id`로 추적해야 함
- **문제**: 힌트 강도 판정에 남은 시간·전체 문제 수·해결 문제 수가 필요함
- **측정 지표**: 세션 생성 성공, 잘못된 session_id 처리, 상태 일관성

## Goal

- 게임마스터가 세션을 만들면 `session_id`와 임시 입장 payload를 반환한다.
- 고객 요청은 같은 세션 상태를 참조한다.
- **Out of Scope**: QR 이미지 UI, 운영용 DB migration 확정, 외부 운영 시스템 직접 호출

## What

**Happy Path**
1. 게임마스터가 `theme_id`, `team_id`로 세션 생성
2. 서버가 UUID 기반 `session_id` 생성
3. 테마의 제한시간/전체 퍼즐 수를 세션에 연결
4. 고객 입장용 임시 payload 반환. QR 이미지는 후속 확장으로 둔다.

**Edge Cases**

| # | 상황 | 처리 |
|---|---|---|
| EC-01 | 존재하지 않는 theme_id | 400 |
| EC-02 | puzzle 데이터 없는 theme | 400 |
| EC-03 | 존재하지 않는 session_id 조회 | 404 |
| EC-04 | 세션 종료 | Agent 응답에서 `CLOSED` |
| EC-05 | 서버 재시작 | 현재 LocalRuntime에서는 유실 — DB 전환 필요 |

## How

```text
POST /api/sessions
GET  /api/sessions/{session_id}
```

P0 기본은 메모리 Runtime이며, `RUNTIME_REPOSITORY=postgres`로 1차 PostgreSQL Repository를 선택할 수 있습니다. 실제 연결·migration·다중 인스턴스 검증은 후속 단계입니다.
<!-- 통합 메모: MVP 임시 입장 방향을 반영하고 QR은 확장 항목으로 남겼습니다. -->

## P0 권한 경계

- 고객 요청은 `session_id`와 `team_id`를 함께 검증한다.
- 세션 소유 팀이 아니면 상태·힌트·정답 조회를 허용하지 않는다.
- 종료·만료 세션은 힌트 제공을 허용하지 않는다.
- 현재 퍼즐이 아닌 미래 퍼즐 요청은 게임마스터 확인 경로로 전환한다.
- `/api/agent`는 고객 요청용, `/api/master/*`는 게임마스터 화면용 경로로 분리한다.
- 게임마스터 요청 생성은 존재하는 세션과 동일한 `team_id`를 요구하고, 상태 변경은 비어 있지 않은 `operator_id`를 기록한다.
- 회원가입·JWT·역할별 서버 인증은 P1 후속 범위다. P0에서는 위 검증을 최소 방어선으로 사용한다.

## AC

**AC-01 · 세션 생성**
- GIVEN: 유효한 theme_id와 team_id
- WHEN: `POST /api/sessions`
- THEN: session_id와 qr_payload 반환

**AC-02 · 잘못된 세션**
- GIVEN: 존재하지 않는 session_id
- WHEN: `GET /api/sessions/{session_id}`
- THEN: 404
