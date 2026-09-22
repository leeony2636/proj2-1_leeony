# MCP 도구 개발 가이드

## 핵심 도구

수정 기획안의 고객 요청/운영 큐 흐름에 직접 필요한 도구는 다음과 같다.

`get_game_session`, `get_puzzle_context`, `get_hint_history`, `get_approved_hint`,
`record_hint_delivery`, `report_equipment_issue`, `request_game_master`,
`get_master_requests`, `update_master_request`

세션 생성·테마 목록 조회는 P0 지원 도구로 유지한다.

## 고객 Agent에 직접 노출하지 않는 상태 변경

- `mark_puzzle_solved`
- 타이머 변경
- 테마 배포

`mark_puzzle_solved` 구현은 내부 Runtime에 남겨 두지만 `FastMCP` 공개 도구 등록에서는 제외한다. 실제 진도 변경은 게임마스터 또는 내부 게임 이벤트 계약이 확정된 뒤 연결한다.

## 원칙

- 입력·출력 필드를 Pydantic schema와 문서에 함께 정의한다.
- 조회 도구는 상태를 변경하지 않는다.
- 쓰기 도구는 멱등성을 보장한다.
- 승인 힌트 조회 실패 시 LLM이 대체 문구를 만들지 않는다.
- P0는 in-process local call이며 별도 network transport로 오인하지 않는다.
- RAG와 LangGraph를 사용하지 않는다.

## 확장

`LocalRuntime`을 기준으로 Escapp/ERCC Adapter를 추가하되, Agent Orchestrator가 특정 Adapter를 직접 알지 않게 한다.
