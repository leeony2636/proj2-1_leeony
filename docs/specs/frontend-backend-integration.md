# Spec — 프론트엔드·FastAPI 연동 초안

> 단계: C안 초안 + B안 고객 세션 연동 1차
>
> 목표: 개발 진행에 따라 B안(고객·게임마스터 실데이터 연동)으로 확장

## 1. 현재 단계: C안 초안 + B안 부분 적용

### 고객 화면

- `frontend/src/api.ts`가 FastAPI 호출과 응답 타입을 담당한다.
- `/customer`는 `POST /api/agent`로 힌트 요청을 전달한다.
- `ANSWER_CONFIRMATION_REQUIRED` 응답이 오면 `offer_id`를 사용해 정답 확인 버튼을 표시한다.
- 정답 확인은 `POST /api/answers/confirm`으로만 수행한다.
- API 실패는 고객용 오류 메시지로 표시하고 임의 힌트를 만들지 않는다.

### 게임마스터 화면

- 현재 `/game-master`의 Escape Ops 화면은 Mock/정적 데모를 유지한다.
- 요청 조회·확인·해결·취소 API 계약을 실제 React 요청 큐 패널에 1차 연결했으며, 정적 Escape Ops 화면은 유지한다.
- 고객 화면과 게임마스터 화면의 API Adapter를 분리해 전환 범위를 제한한다.

## 2. P0 고객 API 계약

### `POST /api/agent`

요청:

```json
{
  "request_id": "req_optional_client_id",
  "session_id": "demo-session",
  "team_id": "demo-team",
  "puzzle_id": "train-p01",
  "message": "힌트 주세요"
}
```

응답 상태:

- `PROVIDE_HINT`: WEAK/STRONG 승인 힌트 제공
- `ANSWER_CONFIRMATION_REQUIRED`: 사용자가 최종 정답을 직접 요구해 일회성 `offer_id` 확인이 필요한 경우
- `NEED_MORE_INFO`: 문제 정보 부족
- `MASTER_REQUEST`: 직원 호출 또는 운영 데이터 누락
- `CLOSED`: 세션 종료·만료
- `ERROR`: 일시 장애 또는 계약 오류

### `POST /api/answers/confirm`

고객이 명시적으로 동의한 경우에만 `offer_id`를 제출한다. 성공 응답의 `policy`는
`USER_EXPLICIT_CONFIRMATION`이어야 하며, 같은 토큰은 재사용할 수 없다.

## 3. 현재 초안의 제한

- 고객 화면은 `POST /api/sessions` 성공 응답의 `session_id`, `team_id`, `current_puzzle_id`를 힌트 요청에 사용한다.
- 테마는 현재 MVP 고정값(`last_train`)이며, 테마 선택 UI는 후속 범위다.
- 테마 선택 UI는 아직 고정값이며, 팀 식별자는 MVP 입력값이다.
- CORS, 인증, 실시간 갱신, 네트워크 재시도 UI는 후속 통합 단계에서 확정한다.

P0 권한 경계는 세션 존재 여부, 요청 팀과 세션 팀의 일치 여부, 게임마스터 상태 변경자의
`operator_id` 비어 있지 않음만 검증한다. `operator_id`가 실제 로그인·역할 권한을 증명하는 것은
아니므로, 외부 배포 전에는 인증 미들웨어와 게임마스터 역할 검증이 필요하다.

## 4. B안 전환 조건

다음 조건을 만족하면 게임마스터 화면을 실제 API로 전환한다.

- [ ] 외부 인증을 포함한 세션·팀·게임마스터 권한 검증 테스트 통과
- [ ] `idempotency_key` 중복 방지와 PostgreSQL 전환 계획 확정
- [x] 게임마스터 요청 큐의 조회·확인·해결·취소 상태 계약 확정
- [ ] 힌트 판정 로그의 고객 개인정보·정답 마스킹 확인
- [x] P0 갱신 방식으로 polling 선택(5초 주기)
- [ ] 고객·게임마스터 API 오류 상태의 UI 문구 확정

## 5. 전환 순서

1. 고객 화면에 실제 세션 생성 응답 연결 — 완료
2. 고객 API 호출의 환경별 Base URL 설정
3. 게임마스터 Mock Adapter를 실제 `/api/master/*` Adapter로 교체 — 요청 큐 패널 1차 완료
4. 세션·직원 호출·힌트 판정 로그를 실제 데이터로 조회
5. 게임마스터 화면의 갱신·오류·권한 경계 검증
6. E2E 테스트와 배포 환경에서 재검증
