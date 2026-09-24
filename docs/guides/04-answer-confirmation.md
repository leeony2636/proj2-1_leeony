# 정답 확인 개발 가이드

## 현재 흐름

1. STRONG 힌트 제공 시 일회성 `offer_id`를 발급한다.
2. 고객 화면은 `ANSWER_CONFIRMATION_REQUIRED`와 버튼을 표시한다.
3. 고객이 `POST /api/answers/confirm`을 호출한다.
4. 서버가 session/team/puzzle/offer 유효성을 확인한다.
5. 성공한 offer는 즉시 소비되어 재사용할 수 없다.

## 금지

- LLM이 정답을 생성하거나 반환하지 않는다.
- `offer_id` 없는 정답 조회를 허용하지 않는다.
- 다른 팀·다른 퍼즐의 offer를 사용하지 못하게 한다.
- 정답을 Langfuse observation이나 일반 MCP 응답에 기록하지 않는다.

## 테스트

정상 동의, 중복 사용, 만료, 팀 불일치, 퍼즐 불일치, 임의 reveal endpoint 부재를 검증한다.
