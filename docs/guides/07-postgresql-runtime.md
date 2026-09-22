# PostgreSQL Runtime 개발 가이드

## 현재 구현

`RuntimeRepository` 계약과 `MemoryRepository`, `PostgresRepository`가 분리되어 있다.
기본값은 `RUNTIME_REPOSITORY=memory`이며 PostgreSQL은 다음 설정으로 선택한다.

```dotenv
RUNTIME_REPOSITORY=postgres
DATABASE_URL=postgresql://app:app@db:5432/app
```

## 저장 대상

세션, 힌트 이벤트, 게임마스터 요청, 멱등성 결과를 `backend/db/schema.sql`에 저장한다.

## 검증 순서

1. 실제 PostgreSQL 연결
2. schema 생성
3. 재시작 후 데이터 보존
4. 동시 멱등성 처리
5. API 두 인스턴스 smoke test

현재 저장소 코드와 설정 테스트는 통과했지만 Docker/실제 DB 연결은 미검증이다.
