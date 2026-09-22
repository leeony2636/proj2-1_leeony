# Domain Source Registry

> 기준: 2026-09-22. 확인 가능한 저장소 내용만 기록한다. 출처 담당자나 라이선스가 확인되지 않은 항목은 임의로 채우지 않는다.

| 자산 | 현재 확인 가능한 출처 유형 | 현재 사용 | 라이선스/권한 기록 | 상태 |
|---|---|---|---|---|
| `docs/01-operations-agent-problem-definition.md` | 팀 수정 기획안 | 문제 정의·MVP/후속 범위·LLM/코드/MCP 역할 경계의 현재 기준 | 팀 내부 기획 문서 | 현재 기준 |
| `skills/SKILL.md` | 사람의 방탈출 현장 경험을 정리한 도메인 규칙 | LLM/코드 경계와 평가 기준 참고 | 저장소에 구체 담당자·동의 범위 기록 없음 | 보강 필요 |
| `backend/data/themes/*.json` | 저장소의 합성 시연 테마 데이터 | LocalRuntime 데모 | 별도 라이선스 기록 없음 | 평가 Ground Truth로 사용 금지 상태 |
| `backend/data/hints/*.json` | 도메인 담당자가 작성·승인한 힌트라는 계약 | MCP 승인 힌트 조회 | 구체 승인자/버전 기록 없음 | 보강 필요 |
| `backend/data/answers/*.json` | AnswerVault용 시연 정답 데이터 | 정답 확인 흐름 | 구체 승인자/버전 기록 없음 | 보강 필요 |
| `mcp_server/adapters/escapp_adapter.py` | 공개 Escapp 구조 참고라는 코드 주석 | 미연결 | URL/라이선스가 현재 저장소에 기록되지 않음 | 실제 연동 전 확인 필요 |
| `mcp_server/adapters/ercc_adapter.py` | ERCC 연동 후보 | 미연결 | API 문서/사용 권한/라이선스 기록 없음 | 실제 연동 전 확인 필요 |

## 적용 원칙

- 2차 프로젝트에서는 RAG를 사용하지 않는다. 도메인 규칙은 `skills/SKILL.md`처럼 고정 Skill로 사용한다.
- 실시간/구조화 데이터가 필요하면 MCP 도구 계약으로 조회한다.
- 출처, 승인자, 사용 권한을 확인하지 못한 외부 데이터를 실제 서비스 Ground Truth로 편입하지 않는다.
- 현재 합성 테마/힌트/정답은 시연 흐름 검증용이며 실제 매장 정답 근거로 과장하지 않는다.
