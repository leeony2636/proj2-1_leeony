# 힌트 강도 정책 개발 가이드

## 정책

- 기본은 `WEAK`이다.
- 남은 시간 15분 이하이고 남은 문제 비율이 50% 이상이면 `STRONG` 후보가 된다.
- 명확한 정답 요구·반복 요청·강한 좌절은 코드 규칙에 따라 `STRONG` 후보가 될 수 있다.
- `STRONG` 힌트는 조건 충족 시 자동 제공한다.
- 최종 정답은 일반 힌트 문장에 포함하지 않는다.

## 역할

LLM은 `direct_answer_request`, `strong_hint_request`, `frustration_high` 같은 신호를 제안한다.
최종 `HintStrength`와 reason code는 `hint_decision.py`가 결정한다.

## 테스트

시간/진도 경계값, 단순 감정 표현, 정답 우회 요구, 반복 요청, 미래 퍼즐 요청을 검증한다.
