# AI Human 7기 — 조별 프로젝트 저장소

이 저장소는 **조별 프로젝트 공간**입니다. 조원 전원이 write 권한을 갖습니다.

## 팀 정보 (프로젝트 시작 시 조장이 작성)

| 항목 | 내용 |
|---|---|
| 프로젝트 | 방탈출 도우미 Agent|
| 조 | 1조 |

## 방탈출 카페 운영 보조 Agent

방탈출 카페에서 발생하는 고객 요청, 힌트 제공, 장비 이상, 게임마스터 호출과 운영 기록을 자연어 기반으로 연결하고, 세션 상태와 운영 정책에 따라 안전하게 처리하는 운영 보조 Agent입니다.

기준 기획안은 [docs/01-operations-agent-problem-definition.md](./docs/01-operations-agent-problem-definition.md)입니다.

### 현재 MVP 처리 흐름

- 고객은 텍스트를 입력하거나 음성 요청 버튼으로 요청을 제출합니다. 상시 마이크 청취는 하지 않습니다.
- STT는 음성을 텍스트로 바꾸는 입력 Adapter입니다. 현재 서비스 구현은 `MockSTTAdapter`이며, 실험상 선택된 `openai/whisper-large-v3-turbo + Escape-room Adapter / Epoch 2`는 아직 실제 Provider로 연결되지 않았습니다.
- LLM/baseline은 요청의 의도·감정·추가정보 필요 여부를 구조화합니다. 힌트 강도·진도·정답 공개·운영 요청 상태를 최종 결정하지 않습니다.
- 코드가 세션·팀·현재 퍼즐·남은 시간·진도·ANSWER 동의를 검증하고 `WEAK`/`STRONG` 정책을 결정합니다.
- MCP/LocalRuntime은 승인 힌트·이력·게임마스터 요청을 조회하거나 기록합니다.
- 장비 이상과 게임마스터 직접 호출은 일반 힌트 경로와 분리해 운영 요청 큐로 보냅니다.
- 게임마스터 요청 상태는 `OPEN → ACKNOWLEDGED → RESOLVED`를 기본 처리 흐름으로 사용하며, 처리 취소가 필요한 경우 `CANCELED`로 종료할 수 있습니다.

### MVP에서 의도적으로 하지 않는 것

- RAG, LangGraph
- LLM의 자유로운 힌트·정답 생성
- 고객 Agent의 진도 직접 변경
- LLM의 직접 타이머·장비 제어
- QR 입장, 예약·결제·환불, CRM, 다중 매장 권한 관리
- CCTV·상시 음성 청취·자동 선제 힌트

현재 `mark_puzzle_solved` Runtime 기능은 내부 테스트/후속 게임 이벤트를 위해 남아 있지만 고객 Agent용 HTTP/MCP 경로에는 공개하지 않습니다. QR 관련 서비스 파일도 후속 확장 참고용일 뿐 현재 API에는 연결하지 않습니다.

### 아직 구현하지 않은 기획 항목

- `GENERAL_INQUIRY`의 최종 응답 계약
- 승인 결과를 LLM이 사용자 친화적 문장으로 다시 표현하는 별도 응답 생성 단계
- 장비 이상 전용 이력 저장소
- 실제 세션 데이터를 이용한 다중 방 운영 현황/우선순위 자동 판정
- 게임 종료 운영 요약·테마별 통계·관리자 기능
- 원격 `/mcp` transport와 실제 ERCC/POS/예약 Adapter

이 항목들은 기획에는 존재하지만 현재 저장소에 승인된 schema·평가 기준·실데이터 계약이 없어 임의 구현하지 않습니다.

## 조원 소개 — 🏁 첫 과제

**조원 각자가 자기 행을 브랜치 → PR → 리뷰 → merge로 직접 추가하세요.** (전원 필수)
이 첫 PR이 협업 흐름 연습입니다. 같은 표를 여러 명이 수정하면 충돌이 날 수 있는데, 그것까지가 연습입니다 (아래 "충돌이 났을 때" 참고).

| 이름 | GitHub | 역할 | 한마디 |
|---|---|---|---|
| 심태현 | @SimonTH-0912 | 팀장 , 최종판단 및 평가 | 잘 부탁드립니다. |
| 하주성 | @leeony2636 | 조원 | 잘 부탁드립니다. |
| 류승민 | @padong47 | 조원 , 미정 | 부족할 수 있지만 열심히 하겠습니다. |
| 박진형 | @jinyeong-731 | 조원, 도메인 | 잘부탁드려요. |
| 서문유신 | @govlgh777-ui | 조원 | 잘 부탁드립니다. |

## 협업 규칙 (필독)

1. **`main`에 직접 push 금지** — 모든 변경은 브랜치 → PR로만 합칩니다.
2-1. 브랜치명: 브랜치 작업 이후 커밋 & 푸시 시 브랜치 명은 **작성자의 성명 이니셜+브랜치생성 순번 조합**으로 커밋 푸시 합니다. ex) **심태현**의 **1번** 브랜치 =  **STH001**
2-2. 파일 수정시 수정내용을 주석으로 표시해주고 관련된 해설 및 이유를 붙여서 작업합니다.
3. PR은 **팀장 + 조원 1명 이상의 approve를 받은 뒤** merge합니다. 리뷰 없는 merge는 감사 리포트에 잡힙니다.
4. **제출물 = 마감 시점의 `main`** — 마감 시각에 강사가 전체 조 repo에 태그를 일괄 생성합니다. 태그 이후 커밋은 평가 대상이 아닙니다.
5. **커밋은 본인 계정으로**: 자기가 한 작업은 자기 계정으로 커밋해야 이 repo가 본인 포트폴리오 증빙이 됩니다. 함께 작업했다면 커밋 메시지에 `Co-authored-by:`를 추가하세요.
6. 다른 조 저장소도 읽을 수 있습니다 — 보고 배우는 것은 권장, 복사 제출은 금지.

## 📁 폴더 구조 (2차 프로젝트)

필수 조건과 제출물에 맞춰 자리를 미리 잡아 두었습니다. 쓰지 않는 것은 지우고, 필요한 것은 더하세요.

```
backend/          FastAPI (필수 2) — services/llm.py 한곳에 LLM 호출을 모읍니다
skills/           도메인 지식·판단 기준 (필수 5)
mcp_server/       MCP 서버 (필수 5)
evals/            평가셋 30건 (필수 4)
EVAL_REPORT.md    개선 전후 지표 (제출물)
docker-compose.yml  `docker compose up` 한 줄 실행 (필수 2)
```

음성 입력을 도입할 때도 STT 호출을 UI나 라우터에 흩뿌리지 않고 별도 Adapter로 격리합니다. STT 결과는 기존 `message` 텍스트 계약으로 들어가며, 원본 음성·전사 전문은 기본 로그와 Langfuse에 저장하지 않습니다.

현재 frontend는 React + TypeScript + Vite 앱이며 `/customer`와 Escape Ops 관제 UI가 연결된 `/game-master` 경로를 제공합니다. 실행 전제와 검증 명령은 [docs/RUN_NOW.md](./docs/RUN_NOW.md)와 [docs/TESTING.md](./docs/TESTING.md)를 참고하세요.

기능별 구현 기준은 [docs/guides/00-development-principles.md](./docs/guides/00-development-principles.md)에서 시작하세요. 세션, STT, 힌트 정책, 정답 동의, 게임마스터, MCP, PostgreSQL, LLM, 프론트엔드, 배포·평가 가이드가 기능별로 분리되어 있습니다.

2026-09-22 기준 Foundation/D3·D4 준비 상태와 미완료 항목은 [docs/FOUNDATION_GATE_2026-09-22.md](./docs/FOUNDATION_GATE_2026-09-22.md)에서 확인합니다. 신뢰 경계는 [docs/TRUST_BOUNDARY.md](./docs/TRUST_BOUNDARY.md), 도메인 출처는 [docs/DOMAIN_SOURCE_REGISTRY.md](./docs/DOMAIN_SOURCE_REGISTRY.md)에 따로 기록합니다. **2차 프로젝트에서는 RAG와 LangGraph를 사용하지 않습니다.**

**착수 후 9/23(수)까지 문제 정의와 `evals/`를 채우세요.** 추석 연휴 전에 이 둘이 있어야 연휴 동안 각자 진행할 수 있습니다.

각 폴더가 무엇이고 무엇을 채워야 하는지는 **[docs/SCAFFOLD.md](./docs/SCAFFOLD.md)**에 정리돼 있습니다.
자세한 요구사항은 2차 프로젝트 가이드를 참고하세요.

## 🔑 시크릿 규칙 (위반 시 전원에게 노출됩니다)

- API 키·비밀번호는 **`.env` 파일에만** 두세요. `.env`는 `.gitignore`에 이미 등록되어 커밋되지 않습니다.
- 코드에 키를 직접 적으면 안 됩니다. 이 org는 상호 공개라 **커밋된 키는 7기 전원이 볼 수 있습니다.**
- 모든 push는 **Secret Scan**(GitHub Actions)이 자동 검사합니다. 검사가 ❌ 실패하면 = 키가 커밋된 것입니다. 즉시 강사에게 알리고 **해당 키를 재발급**하세요. (히스토리에서 지워도 유출된 것으로 간주합니다)
- 필요한 키 목록은 `.env.example`에 값 없이 적어 공유하세요.

## 작업 흐름

```bash
# 1. 최신 main에서 작업 브랜치 생성
git switch main
git pull origin main

# 본인 이니셜 + 브랜치 생성 번호
# 예: 심태현의 첫 번째 브랜치 작업
git switch -c STH001

# 2. 작업 후 커밋·push
git add .
git commit -m "feat: 로그인 API 구현"
git push -u origin STH001

# 3. GitHub에서 Pull Request 생성
# STH001 → main
# 조원 리뷰 및 approve 후 merge
```

브랜치명은 `작성자 성명 이니셜 + 생성 순번`을 사용합니다. 예를 들어 심태현의 네 번째 작업 브랜치는 `STH004`입니다. 브랜치명에 `feat/` 같은 접두사는 붙이지 않습니다.

## 충돌(conflict)이 났을 때

PR 화면에 "This branch has conflicts" 가 뜨면:

```bash
git switch main && git pull          # 최신 main 받기
git switch STH001
# 현재 작업 브랜치명으로 바꿔 입력합니다. 예: git switch STH004
git merge main                       # 충돌 발생 지점이 파일에 표시됨
# 파일 열어 <<<<<<< ======= >>>>>>> 사이에서 남길 내용 선택 후 저장
git add . && git commit              # 충돌 해결 커밋
git push                             # PR이 자동 갱신됨
```

당황하지 말 것 — 충돌은 사고가 아니라 협업의 일상입니다. 막히면 조원 또는 강사를 부르세요.

## 폴더 구조

- `docs/` — 기획서·회의록·발표자료
- `docs/specs/` — 기능별 Spec 문서 (`_example.md` 형식 참고, AI 에이전트에게 구현을 시키기 전 여기에 먼저 작성)
- `AGENTS.md` / `CLAUDE.md` — AI 에이전트(Claude Code·Codex 등) 공통 작업 지침
- 소스 코드 구조는 조에서 자율 결정 (README에 실행 방법 필수 기재)

## 질문

강사 확인이 필요한 질문은 이 저장소의 **Issues**에 남기고 강사를 멘션하세요.
