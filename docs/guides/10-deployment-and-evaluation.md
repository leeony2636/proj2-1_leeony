# 배포·평가 개발 가이드

## P0

Frontend는 Vercel, Backend/FastMCP는 Docker 경계로 둔다. 기본 Runtime은 memory이며 Docker Compose는 로컬 실행 기준이다.

## 후보

- Google Cloud Run + Cloud SQL/PostgreSQL
- Azure Container Apps + Azure PostgreSQL + Azure OpenAI

선택 전에는 비용, 계정, 운영 역량, PostgreSQL 연결·복구·로그 검증을 비교한다.

## 평가

`evals/dataset.jsonl` 30건을 같은 셋으로 반복 실행하고, Provider·모델·Git SHA·정확성·계약 준수율·지연을 기록한다.
실제 외부 Provider·Docker·Langfuse 실행 결과가 없으면 “구현됨”과 “검증됨”을 구분해 기록한다.
