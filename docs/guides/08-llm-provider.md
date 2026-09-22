# LLM Provider 개발 가이드

## 현재 구현

LLM 호출은 `backend/services/llm.py`에 모으고 `LLM_PROVIDER`로 선택한다.
`baseline`은 API key 없이 규칙 기반으로 실행하며, OpenRouter 실패 시 fallback 정책을 사용할 수 있다.

## 역할 제한

LLM은 의도·감정·요청 성격과 MCP 도구 후보만 구조화한다. WEAK/STRONG 최종 결정, 정답 반환,
세션·진도 변경은 담당하지 않는다.

## 후속

Azure OpenAI를 1순위 후보로 비교하되, provider별 출력은 동일한 `IntentResult`로 정규화한다.
Provider 비교 시 정확도뿐 아니라 지연·비용·계약 준수율을 함께 기록한다.
