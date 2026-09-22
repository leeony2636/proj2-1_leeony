# 게임마스터 요청 개발 가이드

## 호출 조건

- 고객이 직원을 직접 요청함
- 장비·소품 이상이 의심됨
- 승인 힌트 데이터가 없음
- 현재 순서 밖 퍼즐 요청 등 운영 판단이 필요함

## 상태 전이

수정 기획안 기준 최초 상태는 `OPEN`이다.

`OPEN → ACKNOWLEDGED → RESOLVED` 또는 `OPEN/ACKNOWLEDGED → CANCELED`만 허용한다.

`CANCELED`는 기획안의 “확인·처리·취소” 요구를 유지하기 위한 종료 상태이며, `RESOLVED`와 마찬가지로 다시 열지 않는다.

## API

- `GET /api/master/requests`
- `POST /api/master/requests/{id}/acknowledge`
- `POST /api/master/requests/{id}/resolve`
- `POST /api/master/requests/{id}/cancel`

모든 상태 변경은 비어 있지 않은 `operator_id`를 요구한다. `idempotency_key`가 주어지면 중복 쓰기를 방지한다.

## 테스트

중복 요청, 잘못된 상태 전이, 세션·팀 불일치, 게임마스터 큐 polling을 검증한다.
