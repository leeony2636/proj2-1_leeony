# 방탈출 운영 보조 Agent Workflow — 현재 기준

```mermaid
flowchart TD
    A[사용자 자연어 요청] --> B[세션/현재 퍼즐/최근 대화/Domain Skill 구성]
    B --> C[INITIAL LLM 판단]
    C --> D{조회가 필요한가?}
    D -->|예| E[선택한 read-only MCP Tool 실행]
    E --> F[Tool Observation을 Context에 추가]
    F --> G[FOLLOWUP LLM 재판단]
    D -->|아니오| H[LLM 결정 검증]
    G --> H
    H --> I[코드 안전/권한 Gate]
    I --> J[승인 힌트/직원 요청/질문 등 실행]
    J --> K[실제 처리와 일치하는 사용자 안내]
```

## 역할 경계

### LLM

- 사용자 의도·복합 요청 의미 판단
- 필요한 조회 Tool 선택
- 정보 부족 시 추가 질문 판단
- Domain Skill/Context/Observation을 함께 보고 `support_need`와 action 결정
- FOLLOWUP에서 조회 전 판단을 유지하거나 근거에 따라 변경

### 코드/MCP

- LLM의 도메인 적절성을 15분/50% 같은 숫자 규칙으로 다시 결정하지 않음
- 세션·권한·현재 퍼즐 검증
- 승인된 힌트만 반환
- ANSWER 별도 동의 경계
- 직원 요청 상태·멱등성
- Pydantic/Policy 계약 검증과 제한된 REPAIR

## Provider 호출

- 조회가 필요 없으면 보통 INITIAL 1회
- 조회가 필요하면 INITIAL + FOLLOWUP
- 계약 오류가 있을 때만 제한된 REPAIR 추가
- Provider 호출은 독립 요청이므로 FOLLOWUP에는 Context, previous decision, Tool results를 다시 전달한다.
