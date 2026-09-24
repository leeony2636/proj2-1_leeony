# 프론트엔드 개발 가이드

## 현재 화면

- `/customer`: 세션 시작, 자연어 힌트 요청, STRONG 후 정답 확인
- `/game-master`: Escape Ops 정적 관제 화면과 실시간 요청 큐

## 원칙

- API 호출은 `frontend/src/api.ts`에 모은다.
- 고객 화면은 `hint_text`가 있을 때만 힌트를 표시한다.
- `ANSWER_CONFIRMATION_REQUIRED` 전에는 정답 버튼과 정답 텍스트를 표시하지 않는다.
- API 실패·네트워크 실패·재시도 상태를 고객용 문구로 분리한다.
- P0 polling 주기는 5초이며, 후속 WebSocket 전환 시 API 계약을 유지한다.

## 검증

Vitest와 `npm run build`를 통과한 뒤 Vercel 환경변수 `VITE_API_BASE_URL`을 확인한다.
