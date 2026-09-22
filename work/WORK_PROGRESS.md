# WORK_PROGRESS

## 확정 결정

- 원본 ZIP은 변경하지 않고 별도 작업 사본에서 수정했다.
- 기존 Domain Skill 연결, 선택적 조회, 최대 1회 LLM 후속 판단 구조는 유지했다.
- RAG/LangGraph/멀티에이전트는 추가하지 않았다.
- `15분/50%` 숫자 규칙과 `재요청 자동 STRONG`은 미확정 상태를 유지했다.
- 승인되지 않은 힌트/정답 생성, 고객 진도 직접 변경, 시간 연장 자동 적용, 장비 직접 조작 금지를 유지했다.
- 실제 외부 LLM/유료 호출, 외부 데이터 쓰기, 배포, Git commit/push/PR/merge는 수행하지 않았다.

## 이번 보완 변경 파일

### 코드
- `backend/services/domain_skill.py`
- `backend/services/llm.py`
- `backend/services/agent_orchestrator.py`
- `backend/services/langfuse_service.py`
- `evals/evaluation_runtime.py` (추가)
- `evals/run_llm_eval.py`
- `evals/run_model_contract_eval.py` (추가)

### Domain Skill
- `skills/SKILL.md`
- `skills/domain_policy.json`

### 테스트
- `backend/tests/test_domain_agent_followup.py`
- `backend/tests/test_langfuse_observation.py`
- `backend/tests/test_llm_normalization_matrix.py` (기존 contract matrix 명칭 정정)

### 문서
- `README.md`
- `EVAL_REPORT.md`
- `docs/PROJECT_PLAN.md`
- `docs/ARCHITECTURE.md`
- `docs/EVALUATION.md`
- `docs/CHANGE_MAP.md`
- `docs/DOMAIN_SOURCE_REGISTRY.md`
- `docs/TRUST_BOUNDARY.md`
- `docs/TEAM_DECISIONS_NEEDED.md`
- `evals/README.md`

## 검증 결과

- `python -m pytest -q` : **167 passed**
- 정규화 기술 테스트: **100 synthetic payload case 통과**
- `python evals/run_llm_eval.py --provider baseline ...` : **30/30 실행 완료, 실패 0**
  - 평가 런타임: 운영 데이터와 분리된 MemoryRuntime
  - 구조적 처리/안내 자동 검사: 30/30 PASS
  - 실제 도메인 품질 점수: 산출하지 않음
- `python evals/run_model_contract_eval.py ...` : **실제 호출 미실행**
  - 상태: `NOT_RUN_EXTERNAL_LLM_APPROVAL_REQUIRED`
  - 현재 입력: 30건, 기본 100건 요구에 미달

## 미검증 / 남은 작업

- 팀 경험자가 판정한 계획서 10문항과 30건 이상 Domain Dataset
- 실제 OpenRouter 전체 서비스 흐름 평가
- 실제 모델 100건 raw 계약 준수/재호출 전후 측정
- Langfuse 외부 Dataset/Prompt 교체·롤백 실제 검증
- PostgreSQL/원격 MCP 실제 통합
- 힌트 강도 정책의 팀 최종 결정
