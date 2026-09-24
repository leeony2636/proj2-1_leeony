# AI Human 7기 — 조별 프로젝트 저장소

이 저장소는 **조별 프로젝트 공간**입니다. 조원 전원이 write 권한을 갖습니다.

## 팀 정보 (프로젝트 시작 시 조장이 작성)

| 항목 | 내용 |
|---|---|
| 프로젝트 | 방탈출 도우미 Agent|
| 조 | 1조 |

## 방탈출 카페 운영 보조 Agent

고객의 힌트·장비 이상·직원 호출·운영 상태 문의를 자연어로 받아, 게임마스터 요청 큐와 안전한 힌트 제공 경로로 연결합니다. 기존 힌트 기능은 운영 보조의 고객 지원 모듈로 유지합니다.

현재 기준은 [운영 보조 기획](./docs/PROJECT_PLAN.md), [현재 상태](./docs/STATUS.md), [미확정 팀 결정](./docs/TEAM_DECISIONS_NEEDED.md)입니다. `skills/domain_policy.json`의 확정 경계/참고 기준을 LLM 입력에 사용하고, LLM은 복합 의도·필요 조회·질문·지원 필요도를 판단합니다. 코드/MCP는 세션 권한, 승인된 WEAK/STRONG 힌트, ANSWER 동의, 직원 요청 상태와 멱등성을 강제합니다. `15분/50%`와 재요청 횟수 기반 자동 STRONG 규칙은 검토 후 **현재 정책에 채택하지 않았습니다**. RAG와 LangGraph는 사용하지 않습니다.

실제 LLM은 `LLM_PROVIDER=openrouter`, 정확한 모델 ID와 별도 키 설정이 필요합니다. `baseline`은 오프라인 구조 smoke/비교용이며 기본 운영 경로에서 자동 대체하지 않습니다. 공식 4모델 선정은 `evals/TEST_POLICY.md`와 `docs/OPENROUTER_ZDR_BUDGET_RUNBOOK.md`를 따르며, ZDR를 강제하고 4개 모델 전체 비용 상한을 `$5`로 둡니다. STT는 Mock Adapter이고, 실제 Provider 품질은 검증되지 않았습니다.

모델 평가를 시작할 팀은 [평가 실행·사람 검토·Langfuse 점수 기록 절차](./docs/EVALUATION.md#팀이-채울-최소-항목과-실행-순서)를 따르세요. 결과 JSON은 검토 작업용이며, 비교·공유할 데이터는 원문을 제외한 CSV와 Langfuse numeric Score로 남깁니다. 현재 `evals/quality_contract_approval.json`은 팀 승인 대기 상태입니다.

STT는 제출된 음성을 텍스트로 바꾸는 선택 입력 경계입니다. 상시 주변 음성을 듣지 않으며, 원본 음성과 전사 전문은 기본 로그/Langfuse에 저장하지 않습니다. STT Provider와 모델은 추후 교체 가능한 Adapter로 둡니다.

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

현재 frontend는 React + TypeScript + Vite 앱이며 `/customer`와 Escape Ops 정적 데모 + 실제 요청 큐 패널이 연결된 `/game-master` 경로를 제공합니다. 정적 데모 데이터는 백엔드 운영 데이터가 아닙니다. 실행 전제와 검증 명령은 [docs/RUN_NOW.md](./docs/RUN_NOW.md)와 [docs/TESTING.md](./docs/TESTING.md)를 참고하세요.

기능별 구현 기준은 [docs/guides/00-development-principles.md](./docs/guides/00-development-principles.md)에서 시작하세요. 세션, STT, 힌트 정책, 정답 동의, 게임마스터, MCP, PostgreSQL, LLM, 프론트엔드, 배포·평가 가이드가 기능별로 분리되어 있습니다.

**착수 후 9/23(수)까지 문제 정의와 `evals/`를 채우세요.** 추석 연휴 전에 이 둘이 있어야 연휴 동안 각자 진행할 수 있습니다.

프로젝트 요구사항은 [2차 프로젝트 기획](./docs/PROJECT_PLAN.md), [현재 상태](./docs/STATUS.md), 실행·검증은 [docs/TESTING.md](./docs/TESTING.md)를 기준으로 확인하세요.

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
