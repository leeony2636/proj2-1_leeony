# 강사 Scaffold × 우리 통합 기획안 적용표

## 그대로 유지한 강사 기본틀

- `.github/PULL_REQUEST_TEMPLATE.md`
- `.github/workflows/secret-scan.yml`
- `CLAUDE.md`
- `EVAL_REPORT.md`
- `docs/SCAFFOLD.md`
- `docs/specs/_example.md`
- `README.md`의 협업 규칙
- `/health`
- `backend/services/llm.py` 단일 LLM 호출 원칙
- `Dockerfile` / `docker-compose.yml` 기본 배치

## 우리 기획안으로 채운 곳

수정 기획안 원문은 `docs/01-operations-agent-problem-definition.md`에 보존하고, 코드/문서 정렬 시 이 파일을 우선 기준으로 사용한다.

| 강사 위치 | 프로젝트 적용 |
|---|---|
| `backend/main.py` | 방탈출 API router 연결 |
| `backend/services/llm.py` | OpenAI/Vertex/Azure 비교용 단일 LLM 진입점 |
| `skills/SKILL.md` | 방탈출 힌트 Domain Skill |
| `mcp_server/` | 세션/퍼즐/힌트/게임마스터 Tool |
| `evals/dataset.jsonl` | 정상·경계·실패 유도 케이스를 포함한 평가셋 30건 |
| `docs/` | Workflow/Architecture/Model Strategy/Status |
| `backend/data/` | 테마/힌트/AnswerVault 자리 |

## 우리 이전 ZIP에서 그대로 가져오지 않은 것

- `.pytest_cache/`, `__pycache__/`, `.pyc`: 실행 캐시이므로 제외
- 별도 `backend/Dockerfile`: 강사 root `Dockerfile`을 기준으로 통합
- 별도 root `requirements.txt`: 강사 `backend/requirements.txt` 기준
- `skill/`: 강사 폴더명 `skills/`에 맞춤
- `shared/`: 강사 구조에 맞춰 `backend/schemas.py`로 통합

## 문서 기준과 실제 구현의 구분

- `docs/specs/mcp-data-contract.md`: 목표 계약과 acceptance criteria를 정의한 Draft 문서
- `mcp_server/tools/`: 현재 FastAPI가 로컬로 호출하는 실제 도구 구현
- `mcp_server/tools_PJH/`: 실험·참고 코드로 운영 경로에 등록하지 않음
- `docs/FUTURE_ARCHITECTURE.md`: P0 이후 Google Cloud Run과 Azure Container Apps를 비교하는 확장 후보
- `docs/guides/`: Foundation 이후 기능별 구현·테스트·확장 기준을 제공하는 개발 가이드
