# 방탈출 Agent Workflow — 데모 확장본

```mermaid
flowchart TD
    A[Game Master 세션 시작] --> B[가상 세션 생성]
    B --> C[고객 자연어 요청]
    C --> D[LLM/분류기: 의도·감정·요청 성격 구조화]

    D -->|장비 이상| E[MASTER_REQUEST]
    D -->|직원 직접 호출| E
    D -->|정보 부족| F[NEED_MORE_INFO]
    D -->|일반/강한/정답 힌트 요청| G[세션·현재 퍼즐 검증]

    G -->|현재 순서 불일치| E
    G --> H[퍼즐·힌트 이력 조회]
    H --> I[코드 기반 WEAK/STRONG 판정]
    I --> J[승인 HintStep 조회]
    J --> K[고객에게 힌트 반환]
    K -->|STRONG 후 사용자 직접 클릭| L[AnswerVault 별도 조회]
    K --> M[HintEvent 기록]
    E --> M
    F --> M
```

## 핵심 경계

- LLM은 자연어 구조화까지만 담당한다.
- 최종 힌트 강도는 `backend/services/hint_decision.py`가 결정한다.
- 일반 힌트 경로에서 AnswerVault를 직접 읽지 않는다.
- 예외 상황은 사람을 제거하지 않고 Game Master 경로로 전환한다.
