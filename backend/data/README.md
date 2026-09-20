# Domain Data

`themes/`, `hints/`, `answers/`에는 최종 확정된 가상 테마 데이터를 넣습니다.

- `themes/`: 테마/퍼즐 메타데이터
- `hints/`: 퍼즐별 승인된 WEAK/NORMAL/STRONG 힌트
- `answers/`: AnswerVault. 일반 Agent/MCP Tool에서 직접 노출하지 않음
- `samples/`: 코드 동작 확인용 샘플. 최종 테마 데이터가 아님

통합 기획안 기준 실제 가상 테마는 2개를 준비할 계획이며,
테마마다 문제 수가 달라도 진도 판정은
`remaining_puzzles / total_puzzles` 비율을 사용합니다.
