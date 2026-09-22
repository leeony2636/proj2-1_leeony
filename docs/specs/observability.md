# 관측·Langfuse 연동 계약

## 현재 상태

- Langfuse SDK 연결 코드가 구현되어 있다.
- `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`가 모두 있을 때만 trace를 전송한다.
- 키가 없거나 Langfuse SDK 오류가 발생하면 Agent는 no-op/fail-open으로 계속 동작한다.
- 실제 프로젝트 trace 확인은 아직 외부 환경에서 검증하지 않았다.

## 기록 허용 필드

- `event_name`
- `request_id`
- `session_id`
- 원본이 아닌 `team_id_hash`
- `puzzle_id`
- 상태·의도·감정·힌트 강도
- `reason_codes`
- 선택 도구·판정 출처
- LLM/STT Provider와 모델명
- STT confidence·상태

## 기록 금지 필드

- `hint_text` 전체
- `answer`, `final_answer`
- `offer_id`
- 원본 음성·전체 전사문
- 고객 개인정보
- 프롬프트 원문과 API Key

`record_event()`는 `AgentResponse.model_dump()`를 직접 전송하지 않고
`ObservationEvent` allowlist를 통해 새 payload를 만든다.

## 환경 변수

```text
LANGFUSE_PUBLIC_KEY=
LANGFUSE_SECRET_KEY=
LANGFUSE_HOST=https://cloud.langfuse.com
LANGFUSE_FLUSH_ON_EVENT=true
```

실제 키는 `.env`에만 저장하며 저장소에 커밋하지 않는다.

## 프롬프트 버전 관리 현재 상태

- 현재 `backend/services/llm.py`의 `SYSTEM_PROMPT`는 코드 문자열이다.
- Langfuse Prompt Management에서 프롬프트를 생성·버전 관리·롤백하는 연결은 아직 구현되지 않았다.
- trace에 사용된 프롬프트 버전을 연결하는 필드/규칙도 아직 확정되지 않았다.
- 따라서 D3의 "Langfuse observation 속성 + 프롬프트 버전 이름 규칙" 중 observation allowlist는 코드로 확인되지만 prompt version 규칙은 팀 합의가 필요하다.
