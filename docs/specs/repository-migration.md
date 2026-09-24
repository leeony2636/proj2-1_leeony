# Runtime Repository 전환 계획

## 현재 결정

`LocalRuntime`은 `RuntimeRepository` 계약만 사용한다. P0 기본값은 `memory`이며,
운영 또는 다중 인스턴스 환경에서만 `RUNTIME_REPOSITORY=postgres`로 전환한다.

| 모드 | 설정 | 용도 | 외부 DB 필요 |
|---|---|---|---|
| P0 Memory | `RUNTIME_REPOSITORY=memory` | 로컬 개발·계약 테스트 | 아니오 |
| B안 PostgreSQL | `RUNTIME_REPOSITORY=postgres` + `DATABASE_URL` | 영속화·다중 인스턴스 | 예 |

## B안 1차 구현 범위

- `sessions`: 세션·진도·종료 상태
- `hint_events`: 힌트 전달 이력과 멱등성 키
- `master_requests`: 게임마스터 요청 큐와 상태 전이
- `idempotency_records`: 중복 요청 재처리 결과
- `PostgresRepository`: MemoryRepository와 동일한 저장 계약 구현
- 시작 시 `schema.sql`을 한 번 적용하는 최소 초기화

## 전환 방법

`.env`에서 아래처럼 설정한 뒤 API를 재시작한다.

```dotenv
RUNTIME_REPOSITORY=postgres
DATABASE_URL=postgresql+asyncpg://app:app@db:5432/app
```

`PostgresRepository`는 현재 `psycopg`를 사용하므로 `+asyncpg` 표기는 기존 환경변수와의
호환을 위해 내부에서 `postgresql://`로 정규화한다. 실제 배포 환경에서는 제공되는
PostgreSQL 연결 문자열 형식을 우선 사용한다.

## 아직 검증하지 않은 항목

- 실제 PostgreSQL 서버에 대한 연결·테이블 생성·재시작 후 데이터 보존
- 두 API 인스턴스가 동시에 같은 멱등성 키를 처리하는 경우
- 운영용 migration 도구와 rollback 정책
- 연결 풀, timeout, retry, secret rotation

따라서 현재 구현은 “B안 Repository 1차 어댑터”이며, 운영 전 통합 테스트와 migration
정책 확정이 필요하다. RAG와 LangGraph는 이 전환 범위에도 포함하지 않는다.
