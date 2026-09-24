# MCP 도구 개발 가이드

## 핵심 도구

`get_game_session`, `get_puzzle_context`, `get_hint_history`, `get_approved_hint`,
`record_hint_delivery`, `report_equipment_issue`, `request_game_master`를 사용한다.

## 원칙

- 입력·출력 필드를 Pydantic schema와 문서에 함께 정의한다.
- 조회 도구는 상태를 변경하지 않는다.
- 쓰기 도구는 멱등성을 보장한다.
- 승인 힌트 조회 실패 시 LLM이 대체 문구를 만들지 않는다.
- P0는 in-process local call이며 별도 network transport로 오인하지 않는다.

## 확장

`LocalRuntime`을 기준으로 Escapp/ERCC Adapter를 추가하되, Agent Orchestrator가 특정 Adapter를 직접 알지 않게 한다.
