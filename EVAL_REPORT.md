# 평가 리포트 - 현재 검증 상태

> 기술 검증, 실제 서비스 흐름 smoke, 실제 모델 품질평가를 분리한다. 합성/Mock 통과를 실제 모델 품질 향상으로 표현하지 않는다.

## 1. 실제로 실행한 검증

| 항목 | 결과 | 의미 |
|---|---|---|
| 백엔드 pytest | **167 passed** | 코드/계약/흐름 기술 검증 |
| 정규화 기술 테스트 | **100 synthetic payload case 통과** | 정규화 enum/action/lookup 계약. 실제 모델 100건 준수율 아님 |
| Domain follow-up 테스트 | 통과 | 선택 조회→2차 LLM 판단, 질문 전환, 세션 격리, 직원 전달 구조 |
| Domain Skill v3 테스트 | 통과 | 위치 혼동 guidance, 문제 번호/전체 문제 수 비공개 경계, 자기보고 rule semantics 확인 |
| baseline 서비스 흐름 | **30/30 실행 완료, 실패 0** | 격리 MemoryRuntime에서 전체 경로 smoke. 도메인 품질 점수 아님 |
| baseline 구조적 처리/안내 검사 | **30/30 PASS** | 실제 처리와 고정 안내 사이의 구조적 모순 검사. 의미 품질 아님 |
| 실제 모델 100건 계약 측정 | **미실행** | 외부 호출 승인 없음 + 현재 입력 30건이라 자동 생성하지 않음 |
| 실제 OpenRouter 서비스 평가 | **미실행** | 외부 호출/비용 승인 및 사람 Ground Truth 필요 |
| 프론트엔드 test/build | 미실행 | 이번 변경 대상이 아니며 의존성 설치를 수행하지 않음 |
| PostgreSQL/원격 MCP | 미실행 | 외부 통합환경 필요 |

`evals/results/model_contract_100.json`에는 실제 호출을 하지 않고 `NOT_RUN_EXTERNAL_LLM_APPROVAL_REQUIRED` 상태가 기록되어 있다.

## 2. 실제 서비스 흐름 평가기

`evals/run_llm_eval.py`는 이제 초기 LLM 판단만 보는 것이 아니라 다음 전체 경로를 평가한다.

`INITIAL → 선택 조회 → FOLLOWUP_AFTER_TOOLS → 코드 검증/격리 처리 → 최종 안내`

- 운영 Repository 대신 평가 전용 `MemoryRepository` 사용
- 외부 Slack은 Mock 유지
- 실제 Provider 사용 시 LLM만 외부 Provider 호출
- Langfuse 외부 전송은 기본 차단
- 실패 row도 결과에 남김
- lookup 선택, 행동 변화, 처리/안내 구조 일치는 자동 기록
- 질문 적절성, 직원 전달 사실성, Skill 규칙의 올바른 적용, 최종 안내 의미 일치는 사람 검토로 남김

## 3. 100건의 의미 정정

`backend/tests/test_llm_normalization_matrix.py`의 100 case는 **정규화 기술 테스트**다.

이는 실제 모델이 100번 계약을 지켰다는 뜻이 아니다. 실제 모델 계약 측정은 `evals/run_model_contract_eval.py`에서 다음을 분리한다.

- 첫 모델 원응답의 raw 계약 준수
- 정규화로 변경된 필드
- 정규화 후 구조화 결과
- 선택한 경우 invalid raw 계약의 1회 재호출 결과

현재 100개 승인 입력이 없고 외부 호출 승인이 없으므로 실제 측정은 미실행 상태다.

## 4. Domain Skill 적용 상태

| 항목 | 현재 값 |
|---|---|
| 코드 Prompt version | `agent-domain-v2.2` |
| Domain Skill version | `2026-09-22.v3` |
| Skill 원문 | `skills/SKILL.md` |
| 실제 LLM 입력용 compact Skill | `skills/domain_policy.json` |
| 위치 혼동 지원 기준 | compact guidance에 연결 |
| 문제 번호/전체 문제 수 비공개 | confirmed boundary에 연결 |
| 숫자/재요청 자동 강도 정책 | 미확정 유지 |
| Langfuse Prompt 원격 교체/롤백 | 미실행 |

`applied_skill_rules`는 LLM이 적용했다고 **보고한** rule id다. 현재 코드는 존재하는 ID만 필터링하며, 실제 규칙 준수 여부는 별도 평가 항목이다.

## 5. 관측 구현

요청 단위로 `request_id`/`session_id`를 공유해 다음 단계를 연결한다.

- INITIAL LLM
- read-only lookup
- FOLLOWUP LLM
- 승인 힌트/직원 요청 같은 실제 처리
- 최종 Agent 결과

LLM 호출에는 provider/model, Prompt/Skill version, stage, latency, token, retry, provider-reported cost를 기록한다. 비용이 제공되지 않으면 `NOT_PROVIDED`이며 0으로 바꾸지 않는다. 힌트 본문, 정답, AnswerVault 토큰, 음성 전사 전문, 고객 원문은 allowlist에 포함하지 않는다.

외부 Langfuse에서 실제 parent trace 구성, Prompt 교체/롤백, Dataset 평가 연결은 아직 검증하지 않았다.

## 6. 실제 개선 효과를 입증하려면 남은 것

1. 팀 경험자가 계획서 10문항(정상3/경계4/실패3)을 작성·판정한다.
2. 같은 기준으로 30건 이상 사람 검증 Domain Dataset을 확정한다.
3. 동일 입력으로 이전 구조/baseline/실제 LLM을 실행한다.
4. 맥락 이해, 질문 적절성, lookup/action 선택, Skill 적용, 직원 전달, 최종 처리 일치를 축별로 비교한다.
5. 실제 모델 100건 계약 준수율이 필요하면 승인된 입력 100건과 외부 호출 승인을 준비한다.

현재 저장소는 이 평가를 실행할 수 있는 경로를 제공하지만 실제 모델 품질 수치는 아직 없다.
