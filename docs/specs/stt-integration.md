# STT 입력 연동 초안

> 상태: Mock Adapter와 Agent 입력 연결 완료
>
> Provider 선정·학습·튜닝: 후속 계획

## 1. 책임 경계

- STT Adapter: 음성 파일을 전사해 `STTResult`를 반환한다.
- STT 품질 정책: 신뢰도·빈 전사·길이를 검사한다.
- LLM: 승인된 `transcript`를 기존 `AgentRequest.message`로 받아 의도·감정을 구조화한다.
- 코드: 남은 시간·진도·힌트 강도·정답 동의·직원 호출을 결정한다.
- MCP: 세션·퍼즐·승인 힌트 조회와 기록을 담당한다.

STT는 힌트 강도나 정답을 결정하지 않는다.

## 2. 현재 API

`POST /api/agent/voice`에 multipart 요청을 보낸다.

필드:

- `audio`: `audio/webm`, `audio/wav`, `audio/mpeg`, `audio/ogg`
- `session_id`
- `team_id`
- `puzzle_id`
- `language` 기본값 `ko-KR`

Mock Adapter에서 품질을 통과한 전사만 기존 Agent 흐름으로 전달된다.

## 3. 실패 정책

| 상태 | 조건 | 후속 처리 |
|---|---|---|
| `ACCEPTED` | confidence >= 0.80, 정상 전사 | LLM/Agent 호출 |
| `CONFIRMATION_REQUIRED` | 0.60 <= confidence < 0.80 | 전사 확인 후 재제출 |
| `RETRY_REQUIRED` | 빈 전사, confidence < 0.60, timeout, 형식 오류, 길이 초과 | LLM/MCP 호출 없이 다시 말하기 |

현재 임계값은 평가 전 초안이며 실제 소음 환경 데이터로 조정한다.

## 4. 보안·관측 경계

- 원본 음성은 Langfuse와 기본 애플리케이션 로그에 기록하지 않는다.
- 정답·힌트 강도는 STT 결과가 결정하지 않는다.
- 낮은 신뢰도나 STT 장애에서 LLM이 빈 입력을 추측하지 않는다.
- Provider와 모델명은 `STTResult`에 기록할 수 있지만 Provider 선정은 확정하지 않는다.

## 5. 후속 계획

1. 실제 소음 환경 평가셋 수집
2. Whisper 계열·Azure Speech·Google Speech 후보 비교
3. p50/p95 지연·한국어 인식률·비용 비교
4. Provider 선정
5. 필요 시 도메인 데이터 기반 학습·튜닝 검토
6. 실제 음성 녹음 UI와 마이크 권한 UX 연결
