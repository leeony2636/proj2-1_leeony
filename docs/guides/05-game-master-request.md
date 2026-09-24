# 게임마스터 요청 개발 가이드

## 호출 조건

- 고객이 직원을 직접 요청함
- 장비·소품 이상이 의심됨
- 승인 힌트 데이터가 없음
- 현재 순서 밖 퍼즐 요청 등 운영 판단이 필요함

## 상태 전이

`PENDING → ACKNOWLEDGED → RESOLVED` 또는 `PENDING/ACKNOWLEDGED → CANCELED`만 허용한다.

## API

- `GET /api/master/requests`
- `POST /api/master/requests/{id}/acknowledge`
- `POST /api/master/requests/{id}/resolve`
- `POST /api/master/requests/{id}/cancel`

모든 쓰기는 `idempotency_key`를 사용하고, operator_id를 요구한다.

## 테스트

중복 요청, 잘못된 상태 전이, 세션·팀 불일치, 게임마스터 큐 polling을 검증한다.
