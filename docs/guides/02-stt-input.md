# STT 입력 개발 가이드

## 현재 구현

`POST /api/agent/voice`가 음성 파일을 받아 `MockSTTAdapter`로 전사한 뒤 기존 Agent 흐름에 전달한다.

## 품질 정책

| 조건 | 처리 |
|---|---|
| confidence >= 0.80 | Agent 입력으로 승인 |
| 0.60 ~ 0.79 | 전사 확인 요구 |
| < 0.60·timeout·지원하지 않는 형식 | 재시도 요구 |

STT는 힌트 강도나 직원 호출을 결정하지 않는다. 전사 승인 후에도 기존 Agent와 코드/MCP 정책을 거친다.

## 후속

Provider 선정, 모델 학습·튜닝, 소음 환경 평가를 별도 비교 작업으로 진행한다. 현재 Mock Adapter를 실제 Provider 성공으로 간주하지 않는다.
