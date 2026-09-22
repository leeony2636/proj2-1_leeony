# Architecture

## P0 구조

기준 문제 정의는 `docs/01-operations-agent-problem-definition.md`이다. 수정 기획안의 운영 보조 Agent 범위를 현재 구현 가능한 P0에 맞춰 적용한다.


```text
Customer / GameMaster UI
          |
          +-- text input ------------------+
          +-- voice submit → STT Adapter --+
                                           v
       FastAPI
          |
          +-- services/llm.py
          |      └─ STT 결과 텍스트의 의도/감정 구조화
          |
          +-- agent_orchestrator.py
          |
          v
      MCP Client
          |
          v
     MCP Tool Layer
          |
          v
      LocalRuntime
```

## STT 입력 경계

- STT는 음성 파일 또는 브라우저 녹음 결과를 텍스트로 변환하는 입력 Adapter다.
- STT는 의도, 감정, 힌트 강도, 정답을 판단하지 않는다. 변환된 텍스트만 `AgentRequest.message`로 전달한다.
- MVP는 고객이 음성 요청 버튼을 눌러 제출하는 방식이며 상시 마이크 청취·선제 개입은 범위에서 제외한다.
- 빈 전사, 낮은 신뢰도, 변환 실패는 LLM/MCP 판정 전에 재입력 요청으로 종료한다.
- Provider와 모델은 `services/stt.py` 또는 동등한 Adapter 경계 뒤에 둔다. 실험상 선택 모델은 `openai/whisper-large-v3-turbo + Escape-room Adapter / Epoch 2`이지만, 현재 서비스 코드는 `MockSTTAdapter`이며 실제 통합은 미완료다.

현재 `MCPClient`는 로컬 함수 호출로 연결된 P0 골격입니다.
실제 FastMCP transport를 붙일 때 `backend/services/mcp_client.py` 내부만 교체하는 방향입니다.

따라서 현재 구조의 `MCP Client` 표기는 네트워크 MCP Client가 아니라 같은 프로세스에서 도구 함수를 호출하는 adapter를 뜻합니다. 별도 FastMCP transport와 다중 인스턴스 운영은 P1 배포 작업으로 분리합니다.

## 외부 Runtime 확장

```text
MCP Tool
  └─ Runtime Adapter
       ├─ LocalRuntime    (P0)
       ├─ EscappAdapter   (후속 검토)
       └─ ERCCAdapter     (후속 검토)
```

외부 제품 API를 Agent가 직접 호출하지 않게 분리합니다.

프론트엔드는 하나의 React + TypeScript + Vite 앱에서 `/customer`와 `/game-master`를 제공하고 Vercel에 정적 배포합니다.
<!-- 통합 메모: temp-git의 정적 HTML 화면 대신 현재 확정된 단일 Vite 앱을 기준으로 설명합니다. -->

## DB

강사 scaffold에는 PostgreSQL 서비스가 기본 포함되어 있습니다.
현재 LocalRuntime은 메모리 저장소이므로 실제 Backend/MCP 분리 배포 전에는
공유 DB 모델로 교체해야 합니다.

## 게임마스터 운영 보조 방향

현재 `/game-master`에는 정적 Escape Ops 데모와 실제 `/api/master/requests` 요청 큐가 함께 존재한다. 정적 데모의 방/시간/진도 값은 실제 Runtime 데이터가 아니므로 운영 판정의 근거로 사용하지 않는다.

팀이 논의한 "카메라 없이 여러 방의 진행 상태를 빠르게 파악"하는 방향은 현재 서버에 이미 존재하는 `SessionState`의 시간·진도, HintEvent 이력, Master Request 상태를 활용하는 범위에서는 기존 구조와 맞는다. 다만 다음이 없어 실제 운영 코파일럿 로직은 아직 구현하지 않는다.

- 전체 활성 세션을 조회하는 Repository/MCP 계약
- 어느 방을 먼저 보아야 하는지에 대한 팀 승인 우선순위 규칙
- 위험도/주의도 점수의 판정 기준과 평가 정답
- 실데이터 기반 운영 화면 검증

카메라/CCTV 영상 분석은 현재 P0 범위 밖이며 새 입력 신호로 추가하지 않는다.

## 상태 변경 경계

- `mark_puzzle_solved`는 Runtime 내부 기능으로 남지만 FastMCP 공개 도구에는 등록하지 않는다.
- 공개 고객 API에도 퍼즐 solve route를 두지 않는다. 진도 변경은 게임마스터 또는 내부 이벤트의 인증/권한 계약이 확정된 뒤 연결한다.
- 게임마스터 요청 상태 변경은 `update_master_request` MCP 도구와 `/api/master/requests/*` API로 분리한다.
- 수정 기획안의 최초 운영 요청 상태는 `OPEN`이며 `OPEN → ACKNOWLEDGED → RESOLVED`를 기본 흐름으로 사용한다. `CANCELED`는 명시적 취소 종료 상태다.

## 입장 경계

MVP는 `session_id` + `team_id` 임시 입장만 사용한다. QR 입장은 후속 확장으로 두며 현재 FastAPI route와 세션 생성 응답에는 QR payload를 포함하지 않는다.

## 기획에는 있으나 P0에서 아직 연결하지 않는 영역

- 일반 문의(`GENERAL_INQUIRY`)의 응답 schema/처리 정책
- LLM의 사용자 친화적 최종 문장 생성 단계
- 장비 이상 전용 장애 이력 저장 구조
- 전체 활성 세션 목록/여러 방 운영 요약/자동 우선순위 규칙
- 게임 종료 리포트·테마별 통계·관리자 화면

이 항목들은 이름·필드·판정 기준을 임의로 만들지 않고 팀 계약이 확정된 뒤 추가한다.
