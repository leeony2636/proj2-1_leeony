# 힌트/지원 판단 정책 개발 가이드 — 현재 기준

## 핵심 원칙

힌트 강도는 단일 숫자나 키워드로 코드가 결정하지 않는다.
LLM이 현재 발화 의미, 세션 Context, 최근 대화, Domain Skill과 필요한 Tool Observation을 함께 보고 `support_need`를 판단한다.

- `STANDARD`: 승인 WEAK 콘텐츠 경계로 매핑
- `STRONG`: 승인 STRONG 콘텐츠 경계로 매핑
- `ANSWER`: 일반 힌트 경로에서 정답을 노출하지 않고 별도 동의/AnswerVault 경계로 연결

`15분/50%` 숫자 규칙과 재요청 횟수만으로 STRONG 자동 승격하는 규칙은 검토 후 현재 정책에 채택하지 않았다.

## 코드 역할

`backend/services/hint_policy.py`는 LLM의 의미 판단을 다시 하지 않는다.
LLM이 선택한 support level을 **승인된 콘텐츠/권한 경계**로만 안전하게 매핑한다.

## 테스트

현재 core-30에서는 강한 감정만 있는 경우, 반복 요청, 이전 힌트 참조, 직접 정답 요구, 내부 진행 정보 요구 등에서 LLM이 Domain Policy를 일반화해 적용하는지 확인한다.
평가 문장 자체를 Prompt/Runtime에 하드코딩하지 않는다.
