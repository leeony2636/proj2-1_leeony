# Current Status

## 바로 실행 가능한 범위
- FastAPI `/health`, `/api/themes`, `/api/sessions`, `/api/agent`
- Vite 고객 화면 `/customer` 및 게임마스터 화면 `/game-master` (Vercel 배포 대상)
- 가상 테마 2개: 교수님의 연구실(12), 마지막 열차(13)
- 각 퍼즐의 WEAK/NORMAL/STRONG 승인 힌트와 AnswerVault 분리
- baseline 기본 실행 및 OpenRouter 선택 연결 코드
- Azure OpenAI 1순위 후보를 위한 환경 변수 자리와 확장 경계
- LLM이 intent/emotion 및 필요한 MCP Tool 후보를 구조화
- 코드 기반 15분 + 남은 문제 50% STRONG 규칙
- 장비 이상/직원 직접 호출 → 게임마스터 큐
- 퍼즐 해결 처리 → 진도 갱신
- MCP Tool Server 코드

## 아직 실제 외부 실행 결과가 없는 항목
- 사용자의 OpenRouter API Key로 실제 `openrouter/free` 호출 성공 여부
- Langfuse 실제 trace 전송
- PostgreSQL 영속화 (현재 P0는 메모리 Runtime)
- Backend가 별도 MCP transport를 통해 서버를 호출하는 네트워크 연결 (현재는 같은 Tool 함수를 로컬 호출)
- GCP Vertex / Azure Foundry Provider 실제 연결
- 최종 평가셋 30건과 100회 계약 테스트
- ERCC/Escapp 실제 연동

## 현재 데모 데이터 주의
두 가상 테마의 퍼즐/힌트/정답 내용은 서비스 흐름 시험을 위한 합성 시연 데이터입니다.
도메인 담당자가 실제 시연용 Ground Truth를 확정하기 전까지 평가 결과의 정답 근거로 사용하지 않습니다.
