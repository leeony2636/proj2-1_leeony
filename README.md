# AI Human 7기 — 조별 프로젝트 저장소

이 저장소는 **조별 프로젝트 공간**입니다. 조원 전원이 write 권한을 갖습니다.

## 팀 정보 (프로젝트 시작 시 조장이 작성)

| 항목 | 내용 |
|---|---|
| 프로젝트 | 방탈출 도우미 Agent|
| 조 | 1조 |

## 방탈출 카페 운영 보조 Agent

방탈출 카페에서 발생하는 고객 요청, 힌트 제공, 장비 이상, 게임마스터 호출과 운영 기록을 자연어 기반으로 연결하고, 세션 상태와 운영 정책에 따라 안전하게 처리하는 운영 보조 Agent입니다.

기준 기획안은 [docs/PROJECT_PLAN.md](./docs/PROJECT_PLAN.md)입니다. 변경 내역은 [docs/CHANGE_MAP.md](./docs/CHANGE_MAP.md), 최종 구조는 [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md)를 기준으로 합니다.

### 현재 MVP 처리 흐름

- 고객 요청은 먼저 세션·팀·현재 퍼즐 경계를 코드로 검증합니다.
- `skills/domain_policy.json`의 버전이 있는 Domain Skill과 최근 대화, 최소 세션 맥락을 LLM에 전달합니다.
- LLM은 단일 라벨만 반환하는 것이 아니라 복합 의도, 필요한 확인 질문, 읽기 전용 조회 도구, 지원 필요도, 후속 행동을 구조화합니다.
- 힌트 이력이나 기존 직원 요청 상태가 필요한 경우에만 LLM이 `get_hint_history` 또는 `get_master_request_status`를 선택합니다.
- 읽기 도구 결과가 생기면 최대 한 번의 `FOLLOWUP_AFTER_TOOLS` LLM 판단으로 실제 후속 행동을 다시 결정합니다.
- 부작용 도구는 코드가 세션·권한·승인 데이터·idempotency를 검증한 뒤 실행합니다.
- 힌트 강도의 **의미 판단**은 LLM이 맡고, `hint_policy.py`는 이를 승인된 `WEAK/STRONG` 데이터 단계로 매핑할 뿐 도메인 적절성을 재판정하지 않습니다.
- 정답은 AnswerVault와 사용자 동의 경계로 분리하며 일반 LLM 응답에 직접 포함하지 않습니다.
- LLM 실패를 키워드 baseline으로 조용히 대체하지 않습니다. baseline은 비교 실험 전용입니다.

### Domain Skill 적용

- `skills/SKILL.md`: 현장 경험과 과거 판단 기준 원문 보존
- `skills/domain_policy.json`: 실제 LLM 입력에 쓰는 compact/버전 자산
- `backend/services/domain_skill.py`: 실제 context 주입과 LLM 자기보고 rule id의 존재 필터링

현재 compact Skill은 `2026-09-22.v3`이며, 위치 혼동 지원 기준과 문제 번호/전체 문제 수 비공개 경계를 실제 LLM 입력에 포함합니다. `15분/50%` 숫자 기반 힌트 강도 규칙과 `재요청 자동 STRONG`은 `unconfirmed_policies`로 유지하고 실행 기준으로 사용하지 않습니다. `applied_skill_rules`는 LLM이 적용했다고 보고한 자기보고 값이며 실제 준수 여부는 별도 평가 대상입니다.

### 코드에 남긴 안전 경계

- 세션·팀·테마 격리, 현재 퍼즐 순서
- 승인된 힌트만 조회, 승인되지 않은 힌트/정답 생성 금지
- AnswerVault/사용자 동의
- 고객 Agent의 진도 직접 변경 금지
- 시간 연장 자동 적용 금지
- 장비 직접 조작 금지
- idempotency와 운영 요청 상태 전이
- LLM/MCP 출력 스키마와 허용 도구 검증

### 평가와 관측

- 백엔드의 100개 합성 payload 테스트는 **정규화 기술 테스트**입니다. 실제 모델 100건 계약 준수율이 아닙니다.
- `evals/dataset.jsonl`의 기존 30건은 **합성 seed**이며 사람 Ground Truth로 사용하지 않습니다.
- `evals/run_llm_eval.py`는 `INITIAL → 선택 조회 → FOLLOWUP → 격리 처리 → 최종 안내` 전체 서비스 흐름을 평가합니다. 운영 데이터 대신 평가 전용 MemoryRuntime을 사용합니다.
- `evals/run_model_contract_eval.py`는 실제 모델의 raw 계약 준수와 정규화 후 결과, 선택적 재호출 전후를 분리해 측정할 수 있습니다. 외부 호출 승인과 필요한 입력이 없으면 미실행 상태로 기록합니다.
- Langfuse allowlist는 같은 request/session 식별자로 LLM·lookup·처리 단계를 연결하며 Prompt/Skill version, model, latency, token, retry, provider가 제공한 cost를 기록합니다. 비용 미제공은 0이 아니라 미제공 상태로 유지합니다. 힌트 본문·정답·토큰·전사 원문·불필요한 고객 원문은 보내지 않습니다.

### 현재 범위에서 하지 않는 것

- RAG, LangGraph, 멀티에이전트
- LLM의 자유로운 힌트·정답 생성
- 고객 Agent의 진도 직접 변경
- LLM의 직접 타이머·장비 제어
- QR 입장, 예약·결제·환불, CRM, 다중 매장 권한 관리
- CCTV·상시 음성 청취·자동 선제 힌트

실제 Provider 품질평가와 실제 모델 100건 계약 측정, PostgreSQL 원격 연동, Langfuse Dataset/Prompt 교체·롤백, 프론트엔드 `npm ci/test/build`는 외부 환경/의존성 또는 팀 데이터가 필요한 항목이므로 완료로 표시하지 않습니다.

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

현재 frontend는 React + TypeScript + Vite 앱이며 `/customer`와 `/game-master` 경로를 제공합니다.

최종 문서는 아래 6개를 기준으로 봅니다.
- [docs/PROJECT_PLAN.md](./docs/PROJECT_PLAN.md) — 문제 정의와 LLM/코드 역할
- [docs/ARCHITECTURE.md](./docs/ARCHITECTURE.md) — 현재 처리 흐름
- [docs/CHANGE_MAP.md](./docs/CHANGE_MAP.md) — 수정·확대·축소·제거 내역
- [docs/EVALUATION.md](./docs/EVALUATION.md) — 평가 계획
- [docs/TRUST_BOUNDARY.md](./docs/TRUST_BOUNDARY.md) — 신뢰 경계
- [docs/TEAM_DECISIONS_NEEDED.md](./docs/TEAM_DECISIONS_NEEDED.md) — 팀 결정이 필요한 미확정 사항

**2차 프로젝트에서는 RAG와 LangGraph를 사용하지 않습니다.**

### 로컬 검증

```bash
# 백엔드 단위/통합 테스트
python -m pytest backend/tests -q

# 합성 seed 전체 서비스 흐름 smoke (실제 도메인 품질 점수 아님)
python evals/run_llm_eval.py --provider baseline --output evals/results/baseline_service_flow.json

# 프론트엔드 (의존성 설치 후)
cd frontend
npm ci
npm test -- --run
npm run build
```

실제 LLM 경로는 `.env.example`을 참고해 환경변수를 설정한 뒤 사용합니다. API 키는 `.env`에만 저장하고 커밋하지 않습니다.
사람이 판정한 실제 Domain Dataset이 준비되기 전에는 합성 seed 결과를 모델 품질 점수로 해석하지 않습니다.

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
