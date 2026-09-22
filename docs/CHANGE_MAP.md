# 변경 요약

현재 구조를 유지하면서 **도메인 기준 적용의 정확성, 전체 서비스 흐름 평가, 요청 단위 관측**에 필요한 부분만 보완했다.

|구분|대상|변경 내용|이유|
|---|---|---|---|
|보완|`skills/domain_policy.json`|v3로 갱신, 위치 혼동 지원 guidance와 문제 번호/전체 문제 수 비공개 경계 추가, visibility 명시|원본 Skill의 현재 적용 기준 누락 보완|
|보완|`backend/services/domain_skill.py`|compact Skill에 visibility/reporting semantics 전달, rule id 필터 의미를 자기보고 ID 존재 확인으로 명확화|rule id 존재와 실제 준수 검증을 구분|
|보완|`backend/services/llm.py`|Prompt v2.2, `applied_skill_rules` 자기보고 의미 명시, raw 계약 검사/정규화 변경 기록, request/session 관측 연결|도메인 기준과 실제 모델 계약 측정 가능성 강화|
|보완|`backend/services/agent_orchestrator.py`|평가 audit hook, lookup/후속 판단/최종 처리 단계 기록, 부작용/실패/재시도 관측 연결|초기 판단부터 최종 안내까지 같은 요청 단위로 평가|
|보완|`backend/services/langfuse_service.py`|trace/request/session, retry/error/tool/cost source allowlist 추가|누락 비용을 0으로 보지 않고 요청 단위 관측 강화|
|추가|`evals/evaluation_runtime.py`|운영 데이터와 분리된 MemoryRuntime 평가 환경|평가 중 외부 부작용/운영 상태 오염 차단|
|확대|`evals/run_llm_eval.py`|INITIAL→lookup→FOLLOWUP→격리 처리→최종 안내 전체 평가|실제 서비스 흐름 평가|
|추가|`evals/run_model_contract_eval.py`|실제 모델 raw 계약/정규화/재호출 전후 측정 수단|합성 100건과 실제 모델 100건을 구분|
|명칭 정정|`test_llm_normalization_matrix.py`|100 synthetic payload를 정규화 기술 테스트로 명시|실제 모델 100건 계약 준수율로 오해 방지|
|유지|선택적 조회/1회 후속 판단|기존 구조 유지|특별한 근거 없이 재설계하지 않음|
|유지|`hint_policy.py`|LLM support_need → 승인 WEAK/STRONG 매핑만 수행|도메인 적절성을 코드가 검증한다고 과장하지 않음|
|유지|AnswerVault/세션·팀/승인 힌트/idempotency/상태 전이|코드 강제 유지|안전·권한·무결성 계약|
|유지|RAG/LangGraph 미사용|구현 범위 제외 유지|현재 프로젝트 범위 유지|

## 줄인/정정한 표현

- `applied_skill_rules`는 “적용 확인 규칙”이 아니라 **LLM이 적용했다고 보고한 규칙**으로 표현한다.
- 100개 합성 payload 테스트는 **정규화 기술 테스트**로만 표현한다.
- baseline 30건 전체 실행은 서비스 경로 smoke이며 실제 도메인 품질 향상으로 표현하지 않는다.
- Prompt version 문자열 기록과 외부 Prompt Management 완료를 구분한다.
- provider가 비용을 주지 않으면 0달러로 기록하지 않는다.
