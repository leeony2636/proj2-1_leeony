# MCP 데이터 계약 및 도구 명세

> 문서 상태: **Draft v0.1.0**
> 최초 작성일: **2026-09-18**
> 주 책임자: **류승민(MCP·데이터), 박진형(MCP·도메인)**
> 연계 담당: **하주성·서문유신(FastAPI), 심태현(평가·Langfuse)**
> 적용 범위: 「방탈출 참가자용 힌트 강도 판단 Agent」 MVP

이 문서는 FastAPI·LLM·MCP 서버·도메인 데이터·평가 코드 사이에서 주고받는 데이터의 형식과 책임을 고정한다. 구현자가 달라도 같은 입력에 같은 구조의 결과를 만들고, 승인되지 않은 힌트나 미래 문제의 정보가 출력되지 않도록 하는 것이 목적이다.

문서에서 **MUST(반드시)**, **MUST NOT(절대 금지)**, **SHOULD(권장)**는 구현 준수 수준을 뜻한다. 아직 팀에서 확정하지 않은 값은 임의로 확정하지 않고 `팀 결정 필요`로 표시한다.

> **현재 구현 정책(2026-09-22):** 일반 WEAK/STRONG 힌트는 코드 정책을 통과하면 자동 제공한다. 사용자가 **최종 정답을 직접 요구한 경우에만** `AnswerVault`가 `offer_id`를 발급하고 `POST /api/answers/confirm`으로 명시적 확인을 거친다. 이 문서의 옛 `OFFERED/ACCEPTED/DECLINED` 예시 중 현재 코드와 일치하지 않는 부분은 아래에서 별도로 표시한다.

## 구현 상태와 이름 매핑

이 문서는 목표 계약인 **Draft v0.1.0**이다. 현재 P0 코드와 도구명이 일부 다르므로, 구현자가 아래 매핑을 확인한 뒤 작업한다. 팀 합의가 끝나면 이 표와 실제 코드 중 하나를 canonical contract로 확정하고 버전을 올린다.

| 계약 문서 이름 | 현재 P0 코드 이름 | 상태 |
|---|---|---|
| `get_game_session` | `get_game_session` | P0 표준 이름 |
| `record_hint_delivery` | `record_hint_delivery` | P0 표준 이름 |
| `request_game_master` | `request_game_master` | P0 표준 이름 |

`idempotency_key` 기반 기록 계약은 현재 MCP 흐름에 사용한다. `offer_id`는 일반 STRONG에 사용하지 않고, 현재 코드에서는 **최종 정답 직접 요청의 확인 토큰**으로 `AnswerVault`에서 사용한다. `OFFERED/ACCEPTED/DECLINED → PROVIDED` 형태의 과거 초안 상태명은 현재 구현과 일치하지 않으므로 canonical contract가 아니다. 현재 MCP 연결은 별도 네트워크 transport가 아닌 로컬 함수 호출이다.

---

## 0. 한눈에 보는 결론

### 0.1 서비스 호출 구조

```text
참가자 입력/버튼
  → (선택) STT Adapter: 음성 → 텍스트·신뢰도 검증
  → FastAPI: 텍스트 요청 스키마 검증·세션 턴 관리
  → LLM: 의도·문제 지칭·명시적 감정 신호 구조화
  → MCP: 세션·진도·문제·힌트 이력·승인 힌트 조회
  → 코드: 시간·진도율·재요청·순서·오류 규칙으로 최종 상태 결정
  → MCP: 힌트 제공/거절/직원 호출 이력 기록
  → LLM: 승인된 내용의 의미와 강도를 바꾸지 않는 범위에서 짧게 표현
  → FastAPI: 출력 계약 검증 후 참가자에게 전달
```

### 0.2 각 구성요소의 책임

| 구성요소 | 해야 하는 일 | 하면 안 되는 일 |
|---|---|---|
| STT | 제출된 음성을 텍스트·신뢰도로 변환 | 상시 청취, 의도·감정·힌트 강도·정답 판단 |
| LLM | 전사 또는 텍스트의 발화 의도, 문제 지칭, 명시적 답답함, 모호성 추출; 승인 문구 자연화 | 힌트 강도 최종 결정, 힌트 창작, 정답 추측, 시간·진도 계산 |
| 코드 | 남은 시간·진도율·재요청 시간 계산; 최종 상태·힌트 강도 결정; 예/아니오 전이 | 승인 데이터가 없을 때 임의 힌트 생성 |
| MCP | 세션·진도·문제·이력·승인 힌트 조회; 이벤트·직원 호출 기록 | LLM처럼 자유 생성, 강도 정책의 임의 변경, 일반 출력으로 정답 반환 |
| Skill | 판단 원칙, 오버라이드, 스포일러 금지, 확인 질문, 직원 호출 기준 | 세션의 실시간 상태를 사실처럼 생성 |
| FastAPI | 외부 API, Pydantic 검증, 요청 ID, 오류 매핑, 전체 흐름 조정 | 도메인 원본 데이터를 검증 없이 그대로 노출 |
| Langfuse | 호출·판정·오류·지연 관측 및 평가 연결 | 정답·전체 승인 힌트·원문 개인정보 기록 |

### 0.3 MVP에서 제공할 MCP 도구

| 도구 | 성격 | 핵심 목적 |
|---|---|---|
| `get_game_session` | 조회 | 세션 상태, 남은 시간, 진도, 현재 문제 확인 |
| `get_puzzle_context` | 조회 | 현재/요청 문제의 순서 접근 가능 여부와 비정답 메타데이터 확인 |
| `get_hint_history` | 조회 | 같은 문제의 최근 힌트 요청·제안·거절·제공 이력 확인 |
| `get_approved_hint` | 조회 | 도메인 담당자가 승인한 약한/강한 힌트 한 건만 조회 |
| `record_hint_delivery` | 기록 | 힌트 요청·제공·실패 이력 기록 |
| `request_game_master` | 기록 | 소품 이상·세팅 오류·직접 호출·비정상 상황을 직원에게 전달 |

`update_progress`는 참가자용 Agent에 바로 노출하지 않는다. 진도 갱신 주체가 확정되기 전까지 게임마스터 UI 또는 별도 내부 API의 책임으로 둔다.

---

## 1. Why — 왜 필요한가

### 1.1 사용자와 상황

- **주 사용자**: 방탈출에 참여 중인 고객
- **보조 사용자**: 게임 세션을 시작하고 비정상 상황을 처리하는 게임마스터
- **상황**: 고객은 친구들과 문제를 풀고 있으므로 Agent와 긴 대화를 할 여유가 없다.
- **요청 방식**: 고객이 짧은 텍스트 또는 음성 제출 버튼으로 요청을 시작한다. Agent가 항상 주변 음성을 듣는 구조는 MVP 범위가 아니다.

### 1.2 해결하려는 문제

1. LLM이 자유롭게 힌트를 만들면 정답이나 다음 문제의 정보가 섞일 수 있다.
2. 남은 시간, 진도, 과거 힌트 이력이 서로 다른 저장소에 있으면 판정이 일관되지 않는다.
3. 같은 요청을 재시도할 때 기록이 중복되면 재요청 판정과 평가 결과가 왜곡된다.
4. STRONG은 코드 정책을 통과하면 자동 제공하고, ANSWER만 별도 동의 절차를 거치도록 분리한다.
5. MCP 조회 실패 시 LLM이 빈칸을 추측하면 승인되지 않은 힌트가 노출된다.
6. FastAPI, MCP, 평가 코드가 서로 다른 필드명과 상태명을 사용하면 통합 단계에서 오류가 발생한다.

### 1.3 MCP 계약으로 얻는 효과

- 승인된 힌트만 식별자와 버전이 있는 데이터로 반환한다.
- 현재 문제보다 뒤의 문제는 MCP 단계에서도 차단한다.
- STRONG은 코드 정책을 통과하면 자동 제공하고, ANSWER 동의 토큰만 서버 상태로 검증한다.
- 모든 쓰기에 멱등성 키를 사용해 중복 기록을 방지한다.
- 같은 오류를 공통 오류 코드로 반환해 FastAPI가 안전한 사용자 메시지로 변환할 수 있다.
- Langfuse 평가에서 `request_id`, `reason_codes`, `data_version`을 기준으로 판정을 재현할 수 있다.

### 1.4 핵심 위험과 방어선

| 위험 | 1차 방어 | 2차 방어 | 실패 시 행동 |
|---|---|---|---|
| 승인되지 않은 힌트 생성 | `get_approved_hint`만 콘텐츠 공급 | 출력 스키마·힌트 ID 검증 | `ERROR`, 임의 생성 금지 |
| 미래 문제 스포일러 | 문제 순서 접근 검사 | 코드에서 현재 순서 재검사 | 현재 문제로 안내 |
| STRONG 정책 우회 제공 | 코드 정책과 승인 힌트 조회 | 응답 강도·힌트 ID 검증 | `ERROR`, 임의 생성 금지 |
| 같은 요청 중복 기록 | `idempotency_key` UNIQUE | 트랜잭션 | 기존 결과 재반환 |
| 세션 만료 후 힌트 | 세션 상태 검사 | FastAPI 상태 검사 | `CLOSED` |
| 소품 오류를 퍼즐 힌트로 오판 | 의도 분류 후 직원 호출 도구 | reason code 평가 | `MASTER_REQUEST` |
| 정답 로그 유출 | 응답 허용 목록·로그 마스킹 | Langfuse 속성 제한 | 기록 중단·보안 보고 |

---

## 2. Goal — 목표와 범위

### 2.1 기능 목표

1. 활성 세션의 남은 시간, 진도율, 현재 문제를 일관된 스키마로 반환한다.
2. 현재 문제에 대해 승인된 약한 또는 강한 힌트만 반환한다.
3. WEAK와 STRONG은 코드 정책을 통과하면 승인 힌트를 자동 조회·제공한다. 사용자가 최종 정답을 직접 요구한 경우에는 `AnswerVault`가 확인 토큰을 발급하고 `/api/answers/confirm`에서 세션·팀·퍼즐·토큰을 검증한 뒤 제공한다.
4. 힌트 요청부터 제공·거절·실패까지의 이력을 시간순으로 저장한다.
5. 소품 이상과 직접 직원 호출을 힌트 이력과 분리해 기록한다.
6. 읽기 실패나 데이터 누락 시 추측 가능한 텍스트 대신 구조화된 오류를 반환한다.
7. 평가와 장애 분석에 필요한 버전·이유 코드·지연 정보를 남긴다.

### 2.2 초기 성공 기준

| 지표 | MVP 목표 | 측정 방법 |
|---|---:|---|
| MCP 성공 응답 스키마 통과율 | 100% | Pydantic 계약 테스트 |
| 승인되지 않은 힌트 출력률 | 0% | `hint_id`·카탈로그 대조 평가 |
| 미래 문제 정보 노출률 | 0% | 순서 역전 실패 유도 테스트 |
| STRONG 승인 콘텐츠 외 제공률 | 0% | 코드 정책·힌트 ID 대조 테스트 |
| 쓰기 중복 생성률 | 0% | 동일 멱등성 키 재호출 테스트 |
| 데이터 조회 실패 시 임의 생성률 | 0% | 장애 주입 평가 |
| 직원 호출 분기 정확도 | 평가셋 기준 기록 | Langfuse score |
| MCP 도구 지연 | 로컬 p95 300ms 이하(초기 목표) | Langfuse span; LLM 시간 제외 |

지연 목표는 개발 장비와 저장소가 결정된 뒤 조정할 수 있다. 안전 관련 0% 목표는 완화하지 않는다.

### 2.3 Out of Scope

- 실제 영업 중인 방탈출 테마의 문제·정답·장치 데이터 수집
- 상시 마이크 청취, 음성으로 먼저 개입하는 기능, STT 원본 음성 보관
- 참가자 주변 음성을 상시 청취해 Agent가 먼저 개입하는 기능
- LLM이 승인 힌트를 처음부터 자유 생성하는 기능
- 결제, 예약, 회원가입, 매장 운영 전체 시스템
- CCTV·IoT 자물쇠·실물 센서 직접 제어
- 여러 매장과 여러 지점의 복잡한 권한 관리
- 직원용 전체 정답 열람 기능
- 연령대별 힌트 규칙의 최종 적용
- 참가자 Agent가 임의로 진도를 변경하는 기능
- ANSWER 자동 제공: MVP에서 비활성. 고객 동의 토큰을 통한 명시적 확인 API만 허용

---

## 3. 확정 사항과 미확정 사항

### 3.1 확정 사항

| 항목 | 확정 내용 |
|---|---|
| 힌트 단계 | `WEAK`, `STRONG` 두 단계 |
| 약한 힌트 | 위치·방향만 안내, 풀이 과정·정답 금지 |
| 강한 힌트 | 풀이 방법을 구체적으로 설명, 최종 정답 금지 |
| 강한 힌트 절차 | 코드 정책을 통과하면 자동 제공 |
| 기본 규칙 | 남은 시간 15분 이하 **AND** 남은 문제 비율 50% 이상이면 강한 힌트 후보, 그 외 약한 힌트 기본 |
| 오버라이드 | 명확한 답답함 또는 같은 문제의 짧은 시간 내 재요청이면 강한 힌트 후보 |
| 애매한 감정 | 감정만으로 강한 힌트를 결정하지 않음 |
| 문제 순서 | 아직 순서가 되지 않은 문제는 힌트 금지 |
| 소품·세팅 오류 | 힌트가 아니라 직원 호출 |
| 콘텐츠 출처 | 도메인 담당자가 작성·승인한 힌트만 MCP로 조회 |
| 일반 출력 | 최종 정답 포함 금지 |

### 3.2 팀 결정 필요

| 결정 항목 | 권장 초안 | 영향 | 확정 담당/시점 |
|---|---|---|---|
| 현재 문제·진도 갱신 주체 | 게임마스터 UI 또는 내부 API | 순서 차단의 신뢰성 | 팀 / 구현 전 |
| 빠른 재요청 기준 | `evals/dataset.jsonl`은 60초 이내를 기준으로 서술하지만 기존 문서 초안에는 120초가 남아 있어 현재 충돌 상태 | 강한 힌트 승격 빈도 | 팀 확정 필요 |
| ANSWER 동의 토큰 유효시간 | **현재 코드 `_OFFER_TTL`은 10분**이고, 기존 문서 초안에는 5분이 남아 있어 정책값은 미확정 | 늦은 정답 확인 처리 | 팀 확정 필요 |
| 거절 후 재제안 억제시간 | 우선 5분 또는 문제 변경 전까지 | 반복 제안 UX | 도메인+평가 |
| 런타임 저장소 | P0 메모리 멱등성, 후속 PostgreSQL Repository | 서버 재시작·다중 인스턴스·복구 | MCP+백엔드 |
| 두 번째 테마 범위 | 카탈로그 스키마는 지원, 전체 데이터 입력은 별도 결정 | 작업량 | 팀 |
| 세션 인증 방식 | `session_id` 외 서명 토큰 추가 권장 | 타 세션 조회 방지 | 백엔드 |
| 최종 정답 확인 액션 | `POST /api/answers/confirm` | 동의 토큰·스포일러·상태 전이 | FastAPI/AnswerVault |

미확정 숫자는 코드 상수가 아니라 환경 변수 또는 설정 객체로 관리한다.

---

## 4. 공통 데이터 계약

### 4.1 표기 규칙

- 필드명은 JSON과 Python 모두 `snake_case`를 사용한다.
- 시간은 서버가 생성한 UTC ISO 8601 문자열을 사용한다. 예: `2026-09-18T06:30:00Z`.
- 비율은 `0.0` 이상 `1.0` 이하의 소수로 저장한다. 화면에서 필요할 때만 백분율로 변환한다.
- 식별자는 의미 있는 접두사와 UUID/ULID를 조합한다.
- 선택 필드는 값이 없으면 `null`로 반환하되, 보안상 숨겨야 하는 필드는 키 자체를 반환하지 않는다.
- 스키마 버전은 응답마다 포함한다. 호환되지 않는 변경은 major 버전을 올린다.
- 서버 계산값을 클라이언트 입력보다 우선한다.

### 4.2 식별자 규칙

| 개체 | 형식 예시 | 생성 주체 |
|---|---|---|
| 요청 | `req_01K5...` | FastAPI, 사용자 턴마다 1개 |
| 멱등성 키 | `req_...:PROVIDED:puz_005` | 호출 조정 코드 |
| 세션 | `ses_01K5...` | 세션 시작 시스템 |
| 테마 | `thm_professor_lab` | 도메인 카탈로그 |
| 문제 | `puz_professor_lab_005` | 도메인 카탈로그 |
| 장치 | `dev_professor_lab_lock_02` | 도메인 카탈로그 |
| 승인 힌트 | `hnt_professor_lab_005_weak_v1` | 도메인 카탈로그 |
| 힌트 이벤트 | `hev_01K5...` | MCP 서버 |
| ANSWER 동의 토큰 | `aof_01K5...` | AnswerVault |
| 직원 호출 | `msr_01K5...` | MCP 서버 |

### 4.3 공통 성공 응답

```json
{
  "ok": true,
  "request_id": "req_01K5EXAMPLE",
  "data": {},
  "meta": {
    "schema_version": "1.0",
    "data_version": "professor_lab@1.0.0",
    "occurred_at": "2026-09-18T06:30:00Z",
    "deduplicated": false
  }
}
```

- `data`는 도구별 출력 모델이다.
- `data_version`은 사용한 도메인 카탈로그 버전이다. 런타임 기록만 다루는 경우에도 해당 세션의 테마 버전을 기록한다.
- `deduplicated=true`이면 같은 멱등성 키의 기존 쓰기 결과를 재반환한 것이다.

### 4.4 공통 실패 응답

```json
{
  "ok": false,
  "request_id": "req_01K5EXAMPLE",
  "error": {
    "code": "APPROVED_HINT_NOT_FOUND",
    "message": "승인된 힌트를 찾을 수 없습니다.",
    "retryable": false,
    "details": {
      "puzzle_id": "puz_professor_lab_005",
      "hint_strength": "WEAK"
    }
  },
  "meta": {
    "schema_version": "1.0",
    "occurred_at": "2026-09-18T06:30:00Z"
  }
}
```

`message`는 내부 서비스가 이해할 수 있는 안전한 설명이다. 참가자에게 그대로 노출하지 않고 FastAPI가 짧은 고객용 문구로 변환한다. `details`에 정답, 승인 힌트 원문, 스택 트레이스를 넣지 않는다.

### 4.5 열거형

```text
SessionStatus       = ACTIVE | CLOSED | EXPIRED
PuzzleAccess        = CURRENT | PAST_SOLVED | DENIED_FUTURE | UNKNOWN
HintStrength        = WEAK | STRONG
HintEventType       = REQUESTED | PROVIDED | FAILED
AnswerOfferStatus   = PENDING | CONSUMED | EXPIRED
MasterRequestReason = PROP_ERROR | SETUP_ERROR | DIRECT_REQUEST | ABNORMAL_STATE | UNKNOWN
MasterRequestStatus = OPEN | ACKNOWLEDGED | RESOLVED | CANCELED
ResponseStatus      = NEED_MORE_INFO | PROVIDE_HINT | ANSWER_CONFIRMATION_REQUIRED |
                      MASTER_REQUEST | CLOSED | ERROR
```

실패 상태 매핑은 다음과 같이 고정한다.

| 상황 | 외부 상태 | `reason_codes` 예시 | 임의 힌트 생성 |
|---|---|---|---|
| 문제·현재 퍼즐 정보 부족 | `NEED_MORE_INFO` | `AMBIGUOUS_REQUEST`, `CURRENT_PUZZLE_REQUIRED` | 금지 |
| 현재 범위 밖·미래 퍼즐·지원하지 않는 요청 | `MASTER_REQUEST` 또는 `NEED_MORE_INFO` | `FUTURE_PUZZLE_BLOCKED`, `OUT_OF_SCOPE_REQUEST` | 금지 |
| MCP·승인 데이터 조회 실패 | `MASTER_REQUEST` 또는 `ERROR` | `APPROVED_HINT_DATA_MISSING`, `APPROVED_HINT_LOOKUP_FAILED` | 금지 |

`MASTER_REQUEST`는 운영자가 확인해야 하는 데이터·장비·진행 문제에 사용하고,
`ERROR`는 재시도 가능한 도구 장애처럼 즉시 운영 요청으로 전환하지 않는 경우에만 사용한다.

### 4.6 판정 이유 코드

`reason_codes`는 사람이 읽는 설명 대신 평가 가능한 고정 문자열 배열이다. 여러 이유가 동시에 적용될 수 있다.

현재 저장소에는 **세 위치의 reason code 명칭이 서로 다르다.** 이 상태에서 한 목록을 임의로 표준화하면 기존 평가 결과와 코드 계약이 깨질 수 있으므로, D4에서 canonical 명칭을 팀이 확정하기 전까지 아래처럼 출처별로 기록한다.

| 출처 | 현재 확인된 예시 | 상태 |
|---|---|---|
| `backend/services/hint_decision.py` | `DEFAULT_WEAK_RULE`, `TIME_PROGRESS_STRONG_RULE`, `DIRECT_ANSWER_REQUEST_STRONG`, `DIRECT_STRONG_HINT_REQUEST`, `HIGH_FRUSTRATION_STRONG` | 현재 실행 코드 |
| `evals/dataset.jsonl` | `BASE_RULE_DEFAULT`, `BASE_RULE_TIME_AND_PROGRESS`, `ANSWER_REQUEST`, `EMOTION_OVERRIDE`, `RE_REQUEST_OVERRIDE` | 현재 평가 정답 데이터 |
| 이 문서의 기존 Draft | `BASE_WEAK`, `TIME_PROGRESS_STRONG`, `EXPLICIT_FRUSTRATION`, `QUICK_REREQUEST` 등 | 과거 계약 초안 |

기본 시간·진도 규칙의 의미는 **남은 시간 15분 이하 AND 남은 문제 비율 50% 이상**이다. 정확히 50%도 STRONG 후보에 포함한다.

`FUTURE_PUZZLE_BLOCKED`, `PROP_OR_SETUP_ERROR`, `DIRECT_MASTER_REQUEST`, `APPROVED_HINT_LOOKUP_FAILED`, `SESSION_NOT_ACTIVE` 등 다른 흐름의 코드도 실제 실행 코드·평가셋과 대조해 canonical 목록을 확정해야 한다. 확정 전에는 이름을 새로 만들거나 일괄 치환하지 않는다.

---

## 5. 핵심 엔터티

### 5.1 Theme

| 필드 | 타입 | 필수 | 제약/설명 |
|---|---|---:|---|
| `theme_id` | string | Y | 전역 유일 |
| `name` | string | Y | 가상 테마명 |
| `difficulty` | integer | Y | 1~5 |
| `total_puzzles` | integer | Y | 1 이상, 실제 문제 수와 일치 |
| `content_version` | string | Y | SemVer 권장 |
| `checksum` | string | Y | 카탈로그 재현용 SHA-256 |
| `is_active` | boolean | Y | 신규 세션 사용 가능 여부 |

초기 후보는 「교수님의 연구실」 12문제와 「마지막 열차」 13문제다. 두 번째 테마의 전체 구현 범위는 팀 결정 전까지 미확정이다.

### 5.2 Puzzle

| 필드 | 타입 | 필수 | 공개 수준 | 제약/설명 |
|---|---|---:|---|---|
| `puzzle_id` | string | Y | 내부/제한 공개 | 테마 내 유일 |
| `theme_id` | string | Y | 내부 | Theme 참조 |
| `order` | integer | Y | 공개 가능 | 1부터 연속, 테마 내 UNIQUE |
| `title` | string | Y | 현재 문제만 | 참가자 화면용 짧은 이름 |
| `goal` | string | Y | 현재 문제만 | 정답을 포함하지 않은 목표 |
| `device_ids` | string[] | Y | 현재 문제만 | 연결 장치 목록 |
| `normal_progress_criteria` | string | Y | 내부 | 완료 판단 기준 |
| `final_answer` | string | Y | **절대 일반 출력 금지** | 가상 문제 정답; 제한 필드 |
| `is_active` | boolean | Y | 내부 | 비활성 문제 조회 차단 |

`final_answer`는 도메인 데이터 요구사항 때문에 저장할 수 있으나 일반 MCP 응답 모델에는 필드가 존재해서는 안 된다. 디버그 로그, Langfuse 입력·출력, 예외 세부 정보에도 포함하지 않는다.

### 5.3 Device

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `device_id` | string | Y | 장치 식별자 |
| `name` | string | Y | 예: 방향 자물쇠 |
| `usage_instructions` | string | Y | 정답과 무관한 조작법 |
| `troubleshooting` | string[] | N | 정상 사용 범위의 확인 절차 |
| `master_required_conditions` | string[] | Y | 파손·미작동 등 직원 호출 조건 |

### 5.4 ApprovedHint

| 필드 | 타입 | 필수 | 제약/설명 |
|---|---|---:|---|
| `hint_id` | string | Y | 버전을 포함한 전역 유일 ID |
| `puzzle_id` | string | Y | Puzzle 참조 |
| `strength` | enum | Y | `WEAK` 또는 `STRONG` |
| `text` | string | Y | 도메인 담당자가 승인한 원문 |
| `must_include` | string[] | N | 자연화 시 보존할 핵심 의미 |
| `must_not_include` | string[] | Y | 정답·미래 문제 등 금지 요소 |
| `content_version` | string | Y | 변경 추적 |
| `approved_by` | string | Y | 승인 담당자 식별자 |
| `approved_at` | datetime | Y | 승인 시각 |
| `is_active` | boolean | Y | 비활성 힌트 반환 금지 |

한 문제에 같은 강도의 활성 힌트가 여러 개라면 선택 규칙이 필요하다. MVP에서는 `(puzzle_id, strength)`당 기본 활성 힌트 1개를 권장한다.

### 5.5 GameSession 및 SessionProgress

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `session_id` | string | Y | 세션 ID |
| `theme_id` | string | Y | 사용 테마 |
| `theme_version` | string | Y | 시작 시점에 고정한 콘텐츠 버전 |
| `status` | enum | Y | ACTIVE/CLOSED/EXPIRED |
| `started_at` | datetime | Y | 서버 시각 |
| `expires_at` | datetime | Y | 타이머 종료 시각 |
| `closed_at` | datetime/null | N | 실제 종료 시각 |
| `current_puzzle_id` | string | Y | 현재 문제 |
| `solved_puzzle_ids` | string[] | Y | 완료 문제 집합 |
| `progress_updated_at` | datetime | Y | 마지막 진도 변경 시각 |

계산 필드:

```text
remaining_seconds = max(0, expires_at - server_now)
solved_count       = len(solved_puzzle_ids)
progress_ratio     = solved_count / total_puzzles
```

클라이언트가 보낸 남은 시간이나 진도율을 그대로 신뢰하지 않는다. 서버의 세션·진도 데이터로 다시 계산한다.

### 5.6 HintEvent

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `event_id` | string | Y | 이벤트 ID |
| `idempotency_key` | string | Y | 전역 UNIQUE |
| `request_id` | string | Y | 한 사용자 턴 추적 ID |
| `session_id` | string | Y | 세션 참조 |
| `puzzle_id` | string | Y | 문제 참조 |
| `event_type` | enum | Y | REQUESTED~FAILED |
| `hint_strength` | enum/null | N | 관련 강도 |
| `response_status` | enum | Y | 외부 응답 상태 |
| `reason_codes` | string[] | Y | 판정 근거 코드 |
| `hint_id` | string/null | N | 실제 승인 힌트 제공 시 필수 |
| `offer_id` | string/null | N | ANSWER 동의 토큰에서만 사용; STRONG에는 사용하지 않음 |
| `occurred_at` | datetime | Y | 서버 생성 |

사용자의 전체 발화 원문은 기본적으로 HintEvent에 저장하지 않는다. 평가에 필요하면 비식별 샘플 ID 또는 해시만 별도 저장한다.

### 5.7 AnswerConsentToken

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `offer_id` | string | Y | ANSWER 동의 토큰 |
| `session_id` | string | Y | 세션 참조 |
| `puzzle_id` | string | Y | 문제 참조 |
| `status` | enum | Y | PENDING~CONSUMED |
| `reason_codes` | string[] | Y | 정답 확인 사유 |
| `offered_at` | datetime | Y | 동의 요청 시각 |
| `expires_at` | datetime | Y | 확인 가능 기한 |
| `resolved_at` | datetime/null | N | 확인·만료 시각 |
| `consumed_at` | datetime/null | N | 정답 공개 완료 시각 |

허용 상태 전이:

```text
PENDING → CONSUMED
PENDING → EXPIRED
```

그 외 전이는 오류다. `EXPIRED`, `CONSUMED` 상태는 다시 `PENDING`으로 바꿀 수 없다.

### 5.8 MasterRequest

| 필드 | 타입 | 필수 | 설명 |
|---|---|---:|---|
| `master_request_id` | string | Y | 직원 호출 ID |
| `idempotency_key` | string | Y | 전역 UNIQUE |
| `request_id` | string | Y | 사용자 턴 추적 ID |
| `session_id` | string | Y | 세션 참조 |
| `puzzle_id` | string/null | N | 관련 문제가 있으면 기록 |
| `reason` | enum | Y | 호출 사유 |
| `summary` | string | Y | 정답 없는 짧은 상황 요약 |
| `status` | enum | Y | 기본 `OPEN` |
| `created_at` | datetime | Y | 서버 생성 |
| `acknowledged_at` | datetime/null | N | 직원 확인 시각 |
| `resolved_at` | datetime/null | N | 처리 완료 시각 |

---

## 6. MCP 도구 상세 계약

모든 도구는 Pydantic 입력·출력 모델을 사용한다. 입력 검증 실패는 도구 본문 실행 전에 거부한다. 도구 설명에는 **언제 호출할지**, **언제 호출하지 않을지**, **부작용**을 명시한다.

### 6.1 `get_game_session`

#### 목적

세션 활성 여부, 서버 기준 남은 시간, 현재 진도, 현재 문제를 한 번에 조회한다. 매 사용자 턴의 첫 MCP 조회로 사용한다.

#### 입력

```json
{
  "request_id": "req_01K5EXAMPLE",
  "session_id": "ses_01K5SESSION"
}
```

#### 성공 `data`

```json
{
  "session_id": "ses_01K5SESSION",
  "theme_id": "thm_professor_lab",
  "status": "ACTIVE",
  "remaining_seconds": 840,
  "current_puzzle_id": "puz_professor_lab_005",
  "current_puzzle_order": 5,
  "solved_count": 4,
  "total_puzzles": 12,
  "progress_ratio": 0.3333,
  "pending_offer": null,
  "recent_declined_offer": {
    "offer_id": "off_01K5OLD",
    "puzzle_id": "puz_professor_lab_005",
    "declined_at": "2026-09-18T06:28:00Z",
    "suppress_until": "2026-09-18T06:33:00Z"
  }
}
```

#### 검증 규칙

- `remaining_seconds`는 요청 시점의 서버 시각으로 계산한다.
- `progress_ratio`는 `solved_count / total_puzzles`로 계산하고 소수점 넷째 자리까지 직렬화한다.
- 시간이 0이면 상태를 `EXPIRED`로 정규화할 수 있다.
- 세션 종료·만료 시 힌트 도구를 후속 호출하지 않고 외부 상태를 `CLOSED`로 결정한다.
- 최근 거절 정보는 같은 강한 제안을 즉시 반복하지 않는 데 사용한다.

#### 주요 오류

- `SESSION_NOT_FOUND`
- `DATA_INTEGRITY_ERROR`: 현재 문제 또는 테마 참조가 깨짐
- `STORAGE_UNAVAILABLE`(재시도 가능)

---

### 6.2 `get_puzzle_context`

#### 목적

현재 문제 또는 사용자가 지칭한 문제의 순서를 확인하고, 접근 가능한 현재 문제일 때만 비정답 메타데이터를 반환한다.

#### 입력

```json
{
  "request_id": "req_01K5EXAMPLE",
  "session_id": "ses_01K5SESSION",
  "requested_puzzle_id": null,
  "requested_order": 7
}
```

`requested_puzzle_id`와 `requested_order`는 둘 중 하나만 사용할 수 있다. 둘 다 없으면 현재 문제를 조회한다.

#### 미래 문제 차단 성공 응답

```json
{
  "access": "DENIED_FUTURE",
  "current_puzzle_id": "puz_professor_lab_005",
  "current_order": 5,
  "requested_order": 7,
  "reason_codes": ["FUTURE_PUZZLE_BLOCKED"]
}
```

차단 응답에는 7번 문제의 제목, 목표, 장치, 힌트, 정답을 포함하지 않는다.

#### 현재 문제 성공 응답

```json
{
  "access": "CURRENT",
  "puzzle_id": "puz_professor_lab_005",
  "order": 5,
  "title": "연구 기록 정리",
  "goal": "현재 놓인 기록에서 다음 단서를 찾는다.",
  "devices": [
    {
      "device_id": "dev_professor_lab_lock_02",
      "name": "방향 자물쇠",
      "usage_instructions": "방향을 순서대로 입력한 뒤 확인 버튼을 누릅니다."
    }
  ],
  "normal_progress_criteria": "연결 장치가 정상적으로 열리면 완료",
  "reason_codes": []
}
```

#### 검증 규칙

- `requested_order > current_order`이면 `DENIED_FUTURE`다.
- 이미 푼 문제는 `PAST_SOLVED`로 표시하되 힌트 조회 가능 여부는 기본적으로 false다.
- 문제를 특정할 수 없으면 `UNKNOWN`을 반환하고 외부 상태는 `NEED_MORE_INFO`가 된다.
- 어떤 경우에도 `final_answer`를 직렬화하지 않는다.

---

### 6.3 `get_hint_history`

#### 목적

같은 문제의 WEAK/STRONG 제공 시점과 최근 재요청 여부를 코드가 판단할 수 있게 한다.

#### 입력

```json
{
  "request_id": "req_01K5EXAMPLE",
  "session_id": "ses_01K5SESSION",
  "puzzle_id": "puz_professor_lab_005",
  "limit": 20
}
```

`limit` 기본값은 20, 허용 범위는 1~100이다.

#### 성공 `data`

```json
{
  "session_id": "ses_01K5SESSION",
  "puzzle_id": "puz_professor_lab_005",
  "events": [
    {
      "event_id": "hev_01K5A",
      "event_type": "PROVIDED",
      "hint_strength": "WEAK",
      "hint_id": "hnt_professor_lab_005_weak_v1",
      "offer_id": null,
      "reason_codes": ["BASE_WEAK"],
      "occurred_at": "2026-09-18T06:27:00Z"
    }
  ],
  "last_weak_hint_at": "2026-09-18T06:27:00Z",
  "seconds_since_last_weak_hint": 180,
  "has_recent_decline": false
}
```

#### 검증 규칙

- 최신 이벤트가 먼저 오도록 `occurred_at DESC`로 반환한다.
- `seconds_since_last_weak_hint`는 서버 시각으로 계산한다.
- 다른 세션의 이력은 절대 반환하지 않는다.
- 힌트 원문은 이력 응답에 포함하지 않는다. 필요하면 `hint_id`로 감사 가능하다.

---

### 6.4 `get_approved_hint`

#### 목적

현재 문제에 연결된 활성 승인 힌트 한 건을 반환한다. 콘텐츠를 얻을 수 있는 유일한 일반 참가자용 MCP 도구다.

#### 약한 힌트 입력

```json
{
  "request_id": "req_01K5EXAMPLE",
  "session_id": "ses_01K5SESSION",
  "puzzle_id": "puz_professor_lab_005",
  "hint_strength": "WEAK",
  "offer_id": null
}
```

#### 강한 힌트 입력

```json
{
  "request_id": "req_01K5EXAMPLE2",
  "session_id": "ses_01K5SESSION",
  "puzzle_id": "puz_professor_lab_005",
  "hint_strength": "STRONG",
  "offer_id": "off_01K5OFFER"
}
```

#### 성공 `data`

```json
{
  "hint_id": "hnt_professor_lab_005_weak_v1",
  "puzzle_id": "puz_professor_lab_005",
  "hint_strength": "WEAK",
  "hint_text": "책장에 놓인 기록의 순서를 다시 살펴보세요.",
  "must_include": ["기록의 순서 확인"],
  "must_not_include": ["최종 번호", "다음 문제 정보"],
  "content_version": "1.0.0",
  "approved": true
}
```

#### 반드시 지킬 검증 순서

1. 세션이 `ACTIVE`인지 확인한다.
2. `puzzle_id`가 세션의 현재 문제인지 확인한다.
3. 요청 강도가 `WEAK` 또는 `STRONG`인지 확인한다.
4. `STRONG`도 별도 동의 없이 승인 힌트를 조회한다.
5. 활성 승인 힌트를 정확히 한 건 조회한다.
6. 응답 모델 허용 목록으로 직렬화한다.
7. 최종 정답 문자열이 힌트 원문에 포함되지 않는지 방어 검증한다.

#### 주요 오류

- `SESSION_NOT_ACTIVE`
- `PUZZLE_ACCESS_DENIED`
- `APPROVED_HINT_NOT_FOUND`
- `SPOILER_VALIDATION_FAILED`

오류가 발생하면 LLM에 대체 힌트 생성을 요청하지 않는다. 외부 상태는 `ERROR` 또는 안전한 `MASTER_REQUEST`로 전환한다.

---

### 6.5 `record_hint_delivery`

> **적용 범위 주의:** 일반 STRONG 자동 제공 경로는 `REQUESTED → PROVIDED`이며 `offer_id`를 요구하지 않는다. 최종 정답 직접 요청의 확인 토큰은 현재 `AnswerVault`와 `POST /api/answers/confirm`에서 별도로 구현되어 있다. 아래 `OFFERED/ACCEPTED/DECLINED` 형태의 과거 예시가 현재 AnswerVault 상태와 다르면 현재 코드 계약을 우선한다.

#### 목적

힌트 흐름의 상태 전이를 원자적으로 기록한다. 쓰기 도구이므로 `idempotency_key`가 필수다.

#### 제공 기록 입력

```json
{
  "request_id": "req_01K5EXAMPLE",
  "idempotency_key": "req_01K5EXAMPLE:PROVIDED:puz_professor_lab_005",
  "session_id": "ses_01K5SESSION",
  "puzzle_id": "puz_professor_lab_005",
  "event_type": "PROVIDED",
  "hint_strength": "STRONG",
  "response_status": "PROVIDE_HINT",
  "reason_codes": ["TIME_PROGRESS_STRONG_RULE"],
  "hint_id": "hnt_professor_lab_005_strong_v1",
  "offer_id": null
}
```

#### 제공 기록 성공 `data`

```json
{
  "event_id": "hev_01K5PROVIDED"
}
```

#### ANSWER 동의 기록

```json
{
  "request_id": "req_01K5ANSWER",
  "idempotency_key": "req_01K5ANSWER:ANSWER_CONFIRMED:puz_professor_lab_005",
  "session_id": "ses_01K5SESSION",
  "puzzle_id": "puz_professor_lab_005",
  "event_type": "ANSWER_CONFIRMED",
  "response_status": "ANSWER_CONFIRMATION_REQUIRED",
  "reason_codes": ["USER_EXPLICIT_CONFIRMATION"],
  "hint_id": null,
  "offer_id": "aof_01K5ANSWER"
}
```

> ANSWER 확인 이벤트는 일반 `record_hint_delivery` MCP 도구가 아니라 `/api/answers/confirm`과 AnswerVault의 후속 감사 계약으로 처리한다.

#### 일반 힌트 제공 기록

```json
{
  "request_id": "req_01K5HINT",
  "idempotency_key": "req_01K5HINT:PROVIDED:puz_professor_lab_005",
  "session_id": "ses_01K5SESSION",
  "puzzle_id": "puz_professor_lab_005",
  "event_type": "PROVIDED",
  "hint_strength": "STRONG",
  "response_status": "PROVIDE_HINT",
  "reason_codes": ["STRONG_AUTO_DELIVERED"],
  "hint_id": "hnt_professor_lab_005_strong_v1",
  "offer_id": null
}
```

#### 이벤트별 필수 필드

| 이벤트 | 추가 필수 | 상태 효과 |
|---|---|---|
| `REQUESTED` | 문제 ID | 요청 이력만 추가 |
| `PROVIDED` | `hint_id`, 강도 | 승인 힌트 제공 기록 |
| `FAILED` | 실패 reason code | 실패 감사 이벤트 추가 |

#### 멱등성·동시성

- `(idempotency_key)`에 UNIQUE 제약을 둔다.
- 같은 키와 같은 payload 재호출은 기존 결과와 `deduplicated=true`를 반환한다.
- 같은 키에 다른 payload가 오면 `IDEMPOTENCY_CONFLICT`를 반환한다.
- ANSWER 동의 토큰 상태 변경은 `/api/answers/confirm`의 별도 계약에서 처리한다.

---

### 6.6 `request_game_master`

#### 목적

소품 이상, 세팅 오류, 사용자의 직접 직원 요청, Agent가 처리할 수 없는 비정상 상태를 직원 호출 큐에 기록한다.

#### 입력

```json
{
  "request_id": "req_01K5MASTER",
  "idempotency_key": "req_01K5MASTER:MASTER_REQUEST:ses_01K5SESSION",
  "session_id": "ses_01K5SESSION",
  "puzzle_id": "puz_professor_lab_005",
  "reason": "PROP_ERROR",
  "summary": "현재 문제의 방향 자물쇠 버튼이 눌리지 않는다고 참가자가 보고함"
}
```

#### 성공 `data`

```json
{
  "master_request_id": "msr_01K5MASTER",
  "status": "OPEN",
  "created_at": "2026-09-18T06:30:00Z",
  "customer_message_key": "MASTER_REQUEST_RECEIVED"
}
```

#### 검증 규칙

- `summary`는 1~300자이며 정답·전체 힌트·비밀정보를 포함하지 않는다.
- 동일 멱등성 키 재호출 시 새로운 직원 호출을 만들지 않는다.
- 세션이 종료되었더라도 안전·소품 문제 보고는 기록할 수 있다. 단, 상태를 함께 표시한다.
- 호출 생성 성공 후 외부 응답 상태는 `MASTER_REQUEST`다.
- 도구 실패 시 실제 접수되지 않았으므로 “직원을 호출했습니다”라고 확정적으로 말하면 안 된다.

---

## 7. 상태별 호출 순서

### 7.1 약한 힌트 제공

```text
1. get_game_session
2. LLM 구조화 결과 확인
3. get_puzzle_context
4. get_hint_history
5. 코드가 WEAK 결정
6. get_approved_hint(WEAK)
7. record_hint_delivery(PROVIDED, WEAK, hint_id)
8. 승인 문구를 짧게 전달
```

`record_hint_delivery`가 실패하면 사용자에게 힌트를 이미 보냈는지 여부가 불명확해진다. 권장 순서는 기록 성공 후 응답 전송이며, 전송 실패는 FastAPI 전송 로그로 별도 추적한다.

### 7.2 STRONG 자동 제공

```text
1. 상태·문제·이력 조회
2. 코드가 STRONG 후보 결정
3. get_approved_hint(STRONG)
4. record_hint_delivery(PROVIDED, STRONG, hint_id)
5. 승인된 강한 힌트 자동 전달
```

정답 직접 요청은 STRONG 자동 제공과 별도다. Agent가 `ANSWER_CONFIRMATION_REQUIRED`와 일회성
`offer_id`를 반환하고, 고객이 `POST /api/answers/confirm`을 호출한 경우에만 AnswerVault가 정답을 공개한다.

### 7.3 ANSWER 동의

```text
1. Agent가 STRONG 힌트를 먼저 자동 제공
2. ANSWER_CONFIRMATION_REQUIRED와 일회성 offer_id 발급
3. 고객이 POST /api/answers/confirm 호출
4. 세션·팀·퍼즐·만료·재사용 여부 검증
5. 검증 성공 시 토큰을 소비하고 정답 반환
```

### 7.5 미래 문제 요청

```text
1. LLM이 요청 순서/문제 식별
2. get_puzzle_context(requested_order)
3. DENIED_FUTURE 확인
4. 힌트 조회 없이 현재 문제로 안내
5. 필요하면 FAILED 또는 REQUESTED 이벤트에 FUTURE_PUZZLE_BLOCKED 기록
```

### 7.6 소품 오류·직원 직접 요청

```text
1. 세션 확인
2. request_game_master
3. 성공했을 때만 접수 완료 응답
4. 힌트 도구는 호출하지 않음
```

### 7.7 MCP 조회 실패

```text
1. retryable=true인 읽기 오류만 짧은 제한 재시도
2. 계속 실패하면 ERROR
3. LLM 임의 힌트 생성 금지
4. 장애가 게임 진행을 막으면 직원 연결 선택지 제공
```

---

## 8. 오류 계약

| 오류 코드 | HTTP 매핑 예시 | 재시도 | 외부 처리 |
|---|---:|---:|---|
| `INVALID_ARGUMENT` | 422 | N | 입력을 짧게 다시 확인 |
| `SESSION_NOT_FOUND` | 404 | N | 세션 확인 요청 |
| `SESSION_NOT_ACTIVE` | 409 | N | `CLOSED` |
| `PUZZLE_NOT_FOUND` | 404 | N | `NEED_MORE_INFO` |
| `PUZZLE_ACCESS_DENIED` | 403 | N | 현재 문제로 안내 |
| `APPROVED_HINT_NOT_FOUND` | 404 | N | `MASTER_REQUEST`, 임의 생성 금지 |
| `APPROVED_HINT_LOOKUP_FAILED` | 503 | Y | 1회 재시도 후 `ERROR` |
| `ANSWER_CONFIRMATION_INVALID` | 403 | N | 정답 미공개 |
| `ANSWER_CONFIRMATION_EXPIRED` | 403 | N | 정답 미공개 |
| `ANSWER_CONFIRMATION_REUSED` | 403 | N | 중복 공개 차단 |
| `IDEMPOTENCY_CONFLICT` | 409 | N | 개발 오류 기록, 처리 중단 |
| `SPOILER_VALIDATION_FAILED` | 500 | N | 출력 차단·보안 이벤트 |
| `DATA_INTEGRITY_ERROR` | 500 | N | 출력 차단·직원 연결 고려 |
| `STORAGE_UNAVAILABLE` | 503 | Y | 제한 재시도 후 `ERROR` |
| `INTERNAL_ERROR` | 500 | 조건부 | 일반 오류, 세부정보 숨김 |

MCP는 참가자용 자연어를 책임지지 않는다. FastAPI가 오류 코드를 `CLOSED`, `NEED_MORE_INFO`, `MASTER_REQUEST`, `ERROR` 등 외부 응답 상태로 매핑한다.

---

## 9. 저장 구조와 무결성

### 9.1 권장 디렉터리

```text
mcp_server/
  server.py                 # FastMCP 도구 등록만 담당
  models/
    common.py               # 공통 envelope, enum, error
    catalog.py              # Theme, Puzzle, Device, ApprovedHint
    runtime.py              # Session, Event, Offer, MasterRequest
  tools/
    session.py
    puzzle.py
    hint.py
    master.py
  repositories/
    protocols.py            # 저장소 인터페이스
    memory.py               # 단위 테스트용
    sql.py                  # 저장소 확정 후 구현
  services/
    access_policy.py        # 문제 순서 접근 검사
    spoiler_guard.py        # 정답 포함 여부 방어 검사
    idempotency.py
  data/
    themes/
      professor_lab.v1.json
      last_train.v1.json
  tests/
    contract/
    integration/
```

### 9.2 논리 테이블/컬렉션

| 저장 단위 | 주요 키·제약 |
|---|---|
| `themes` | PK `theme_id`; UNIQUE `(theme_id, content_version)` |
| `puzzles` | PK `puzzle_id`; UNIQUE `(theme_id, order, content_version)` |
| `devices` | PK `device_id` |
| `approved_hints` | PK `hint_id`; INDEX `(puzzle_id, strength, is_active)` |
| `game_sessions` | PK `session_id`; theme version 고정 |
| `session_progress` | PK/FK `session_id`; 현재 문제 FK |
| `hint_events` | PK `event_id`; UNIQUE `idempotency_key`; INDEX `(session_id, puzzle_id, occurred_at)` |
| `strong_hint_offers` | PK `offer_id`; INDEX `(session_id, puzzle_id, status)` |
| `master_requests` | PK `master_request_id`; UNIQUE `idempotency_key`; INDEX `(status, created_at)` |

### 9.3 데이터 불변식

1. `total_puzzles`는 해당 버전의 활성 Puzzle 수와 같아야 한다.
2. 문제 `order`는 1부터 시작하고 중복될 수 없다.
3. 각 활성 문제에는 약한 힌트와 강한 힌트가 최소 1개씩 있어야 한다.
4. 승인 힌트의 `puzzle_id`는 존재하는 활성 문제를 참조해야 한다.
5. 승인 힌트 텍스트에는 해당 문제의 `final_answer`가 포함될 수 없다.
6. 세션의 `current_puzzle_id`는 세션의 테마·버전에 속해야 한다.
7. `solved_puzzle_ids`는 중복될 수 없고 현재 문제보다 뒤의 문제를 포함해서는 안 된다.
8. `progress_ratio`는 저장하지 않고 조회 시 계산하는 것을 권장한다.
9. STRONG `PROVIDED` 이벤트에는 코드 판정과 활성 STRONG hint가 있어야 한다.
10. ANSWER 동의 토큰은 최대 한 번만 CONSUMED 될 수 있다.

### 9.4 카탈로그 버전과 변경 절차

- 도메인 JSON 변경 시 `content_version`과 SHA-256 `checksum`을 갱신한다.
- 진행 중인 세션은 시작 당시 `theme_version`에 고정한다.
- 단순 오탈자 수정도 평가 재현성에 영향을 주면 patch 버전을 올린다.
- 강도나 의미가 바뀌는 힌트 변경은 최소 minor 버전을 올린다.
- 기존 `hint_id`의 의미를 덮어쓰지 않고 새 버전 ID를 생성한다.
- 변경 PR에는 도메인 담당 승인과 관련 회귀 테스트 결과를 남긴다.

---

## 10. Pydantic·FastMCP 구현 규칙

1. 모든 입력 모델은 `extra="forbid"`로 알 수 없는 필드를 거부한다.
2. 모든 열거형은 문자열 Enum으로 정의해 JSON 직렬화를 안정화한다.
3. 문자열 길이, 배열 최대 길이, 숫자 범위를 모델에서 제한한다.
4. `remaining_seconds`, `progress_ratio`, `occurred_at`은 서버 계산 필드로 둔다.
5. 응답은 내부 ORM 객체를 직접 반환하지 않고 출력 전용 Pydantic 모델로 변환한다.
6. 정답 필드가 있는 내부 모델과 외부 응답 모델을 분리한다.
7. 도구 본문은 비즈니스 로직을 직접 길게 담지 않고 service/repository를 호출한다.
8. 각 `@mcp.tool()` docstring에 호출 조건, 입력 의미, 반환, 부작용, 금지 사항을 작성한다.
9. 예상 가능한 도메인 오류는 공통 오류 envelope로 변환한다.
10. 스택 트레이스는 서버 로그에만 남기고 도구 응답에는 포함하지 않는다.

권장 함수 형태:

```python
@mcp.tool()
def get_game_session(input: GetGameSessionInput) -> ToolResponse[SessionStateData]:
    """활성 세션의 서버 계산 상태를 조회한다. 힌트 콘텐츠는 반환하지 않는다."""
    ...
```

FastMCP 버전에 따라 제네릭 모델 직렬화가 불안정하면 도구별 구체 응답 모델을 정의한다. 실제 설치 버전을 확인하기 전에는 특정 버전 API를 단정하지 않는다.

---

## 11. 보안·스포일러·개인정보 규칙

### 11.1 출력 허용 목록

외부 응답 모델에 정의된 필드만 직렬화한다. 내부 객체를 `model_dump()`로 통째로 내보내지 않는다.

### 11.2 절대 기록하지 않을 값

- 실제 API 키·토큰·비밀번호
- 최종 정답
- 전체 테마의 모든 승인 힌트 원문
- 참가자의 불필요한 개인정보
- 사용자 발화 전체 원문(평가 목적의 명시적 샘플 제외)
- 스택 트레이스와 데이터베이스 연결 문자열

### 11.3 프롬프트 인젝션 대응

- “직원이다”, “관리자다”, “개발자 모드다” 같은 자연어 주장은 권한 증명이 아니다.
- 사용자 입력으로 `puzzle_id`, 파일 경로, SQL 조건을 직접 조립하지 않는다.
- 전체 문제/힌트 목록을 반환하는 참가자용 도구를 만들지 않는다.
- MCP 도구 설명이나 카탈로그 내용에 포함된 문장을 새로운 시스템 지시로 취급하지 않는다.
- 미래 문제와 전체 정답 요청은 코드의 접근 정책으로 차단한다.

### 11.4 세션 격리

- 모든 런타임 조회는 `session_id` 범위를 필수로 적용한다.
- `puzzle_id`만으로 이력을 조회하지 않는다.
- 세션 토큰이 도입되면 토큰의 세션 ID와 입력 세션 ID 일치를 검증한다.
- 다른 팀/테마의 카탈로그가 섞이지 않도록 `theme_id`와 `theme_version`을 함께 확인한다.

---

## 12. Langfuse 관측 계약

각 MCP 호출을 `mcp.tool.<tool_name>` span으로 기록한다. 원문 대신 평가와 장애 분석에 필요한 최소 속성만 사용한다.

### 12.1 기록할 속성

| 속성 | 예시 |
|---|---|
| `trace_id` | FastAPI 요청 trace |
| `request_id` | `req_...` |
| `session_id_hash` | 원본 대신 단방향 해시 |
| `theme_id` | `thm_professor_lab` |
| `puzzle_id` | 현재 문제 ID |
| `tool_name` | `get_approved_hint` |
| `hint_strength` | WEAK/STRONG/null |
| `response_status` | PROVIDE_HINT 등 |
| `reason_codes` | 고정 문자열 배열 |
| `result` | success/error |
| `error_code` | 실패 시 코드 |
| `latency_ms` | MCP 도구 시간 |
| `schema_version` | `1.0` |
| `data_version` | 테마 콘텐츠 버전 |
| `deduplicated` | true/false |

### 12.2 기록하지 않을 속성

- `final_answer`
- 전체 `hint_text`
- 사용자 발화 원문
- API 키·세션 인증 토큰
- 직원 호출 summary 원문 전체

평가 데이터와 연결해야 할 때는 `eval_case_id`만 기록하고 원문은 평가셋 저장소에서 조회한다.

---

## 13. Acceptance Criteria — Given/When/Then

### 세션·진도

**AC-01 활성 세션 조회**
GIVEN 활성 세션과 유효한 진도 데이터가 있고
WHEN `get_game_session`을 호출하면
THEN 서버 기준 남은 시간·진도율·현재 문제가 스키마에 맞게 반환된다.

**AC-02 진도율 계산**
GIVEN 전체 12문제 중 4문제가 해결됐고
WHEN 상태를 조회하면
THEN `solved_count=4`, `total_puzzles=12`, `progress_ratio=0.3333`이다.

**AC-03 종료 세션**
GIVEN 세션이 CLOSED 또는 EXPIRED이고
WHEN 힌트 흐름이 시작되면
THEN 힌트를 반환하지 않고 외부 상태가 `CLOSED`가 된다.

### 문제 순서·스포일러

**AC-04 현재 문제 조회**
GIVEN 현재 문제가 5번이고
WHEN 현재 문제 컨텍스트를 조회하면
THEN 5번의 비정답 메타데이터만 반환된다.

**AC-05 미래 문제 차단**
GIVEN 현재 문제가 5번이고
WHEN 7번 문제를 요청하면
THEN `DENIED_FUTURE`이며 7번의 제목·목표·장치·힌트·정답은 반환되지 않는다.

**AC-06 정답 직렬화 금지**
GIVEN 내부 Puzzle에 `final_answer`가 있고
WHEN 모든 조회 도구 응답을 직렬화하면
THEN 응답 JSON 어디에도 필드명과 값이 나타나지 않는다.

### 승인 힌트

**AC-07 약한 힌트 성공**
GIVEN 현재 문제에 활성 승인 약한 힌트가 있고
WHEN WEAK 조회를 하면
THEN `approved=true`와 정확한 `hint_id`가 반환된다.

**AC-08 승인 힌트 누락**
GIVEN 현재 문제의 승인 약한 힌트가 없고
WHEN WEAK 조회를 하면
THEN `APPROVED_HINT_NOT_FOUND`를 기록하고 `MASTER_REQUEST`로 전환하며 대체 문구를 생성하지 않는다.

**AC-09 STRONG 자동 제공**
GIVEN 수락된 offer가 없어도 코드 정책이 STRONG을 결정했고
WHEN 승인 STRONG 힌트를 조회하면
THEN 별도 동의 없이 승인된 힌트 한 건을 반환한다.

**AC-10 ANSWER 동의 전 정답 차단**
GIVEN 유효한 ANSWER 동의 토큰이 없고
WHEN 정답 확인을 요청하면
THEN `403`이며 정답 문자열은 반환되지 않는다.

**AC-11 ANSWER 토큰 만료 차단**
GIVEN ANSWER 동의 토큰이 만료되었고
WHEN 정답 확인을 요청하면
THEN 오류를 반환하고 콘텐츠는 반환하지 않는다.

**AC-12 ANSWER 토큰 재사용 차단**
GIVEN ANSWER 동의 토큰이 이미 CONSUMED 상태이고
WHEN 다시 같은 토큰으로 정답 확인을 요청하면
THEN `403`이 되고 정답은 반환되지 않는다.

### 이력·재요청·멱등성

**AC-13 이력 정렬**
GIVEN 같은 문제의 이벤트가 여러 건 있고
WHEN 이력을 조회하면
THEN 최신 이벤트부터 반환된다.

**AC-14 재요청 계산 자료**
GIVEN 같은 문제에 약한 힌트를 이미 제공했고
WHEN 이력을 조회하면
THEN 마지막 약한 힌트 시각과 경과 초가 서버 기준으로 반환된다.

**AC-15 STRONG 자동 제공**
GIVEN 코드가 강한 힌트 후보를 결정했고
WHEN 승인 힌트를 조회하면
THEN 동의 토큰 없이 `PROVIDED` 이벤트를 기록하고 STRONG을 전달한다.

**AC-16 ANSWER 동의 토큰**
GIVEN 고객이 유효한 `offer_id`로 정답 확인을 요청했고
WHEN `/api/answers/confirm`을 호출하면
THEN 토큰을 한 번 소비하고 정답을 반환한다.

**AC-17 동일 쓰기 재호출**
GIVEN 이미 처리한 `idempotency_key`와 동일 payload이고
WHEN 쓰기 도구를 재호출하면
THEN 새 행을 만들지 않고 기존 결과와 `deduplicated=true`를 반환한다.

**AC-18 멱등성 충돌**
GIVEN 같은 `idempotency_key`에 다른 payload이고
WHEN 쓰기 도구를 호출하면
THEN `IDEMPOTENCY_CONFLICT`로 거부한다.

**AC-19 ANSWER 토큰 재사용**
GIVEN 이미 소비된 ANSWER 토큰을 다시 사용하고
WHEN `/api/answers/confirm`을 호출하면
THEN `403`으로 거부하고 정답을 반환하지 않는다.

### 직원 호출·오류

**AC-20 소품 오류 직원 호출**
GIVEN 참가자가 소품 미작동을 명확히 보고했고
WHEN `request_game_master`가 성공하면
THEN OPEN 호출 한 건이 생성되고 외부 상태는 `MASTER_REQUEST`다.

**AC-21 직원 호출 중복 방지**
GIVEN 네트워크 재시도로 같은 호출을 다시 전송했고
WHEN 동일 멱등성 키를 사용하면
THEN 직원 호출은 한 건만 존재한다.

**AC-22 직원 호출 저장 실패**
GIVEN 저장소 장애로 호출 생성이 실패했고
WHEN 사용자 응답을 만들면
THEN 접수 완료라고 말하지 않고 실패 또는 대체 연락 안내를 반환한다.

**AC-23 MCP 장애 시 임의 생성 금지**
GIVEN 승인 힌트 조회가 실패했고
WHEN LLM 응답 단계로 이동하려 하면
THEN 힌트 생성을 중단하고, 데이터 누락은 `MASTER_REQUEST`, 일시 장애는 1회 재시도 후 `ERROR` 처리한다.

### 계약·관측

**AC-24 알 수 없는 입력 거부**
GIVEN 계약에 없는 필드가 입력됐고
WHEN Pydantic 검증을 하면
THEN 도구 본문 실행 전에 422/`INVALID_ARGUMENT`으로 거부된다.

**AC-25 관측 정보 마스킹**
GIVEN 힌트와 정답이 포함된 내부 객체가 있고
WHEN Langfuse span을 기록하면
THEN 식별·판정 메타데이터만 기록되고 정답과 힌트 원문은 없다.

**AC-26 데이터 재현성**
GIVEN 평가를 실행했고
WHEN 결과를 확인하면
THEN `schema_version`, `data_version`, `checksum`, `eval_case_id`로 사용 데이터를 재현할 수 있다.

---

## 14. 테스트 전략

### 14.1 테스트 계층

| 계층 | 대상 | 예시 |
|---|---|---|
| 단위 테스트 | 계산·상태 전이·스포일러 검사 | 진도율, ANSWER 토큰 상태, 정답 포함 탐지 |
| 계약 테스트 | Pydantic 입출력 | 필수 필드, enum, extra forbid, 오류 envelope |
| 저장소 테스트 | 멱등성·트랜잭션 | 중복 쓰기, 동시 수락/거절 |
| MCP 통합 테스트 | FastMCP 도구 호출 | 6개 도구 happy/edge/failure |
| FastAPI 연동 테스트 | 외부 상태 매핑 | MCP 오류→ERROR, 미래 문제→안내 |
| 평가 회귀 | 30건 평가셋 | 강도·오버라이드·스포일러·직원 호출 |

### 14.2 최소 테스트 파일 제안

```text
mcp_server/tests/contract/test_session_contract.py
mcp_server/tests/contract/test_puzzle_access_contract.py
mcp_server/tests/contract/test_hint_contract.py
mcp_server/tests/contract/test_error_contract.py
mcp_server/tests/test_offer_state_machine.py
mcp_server/tests/test_idempotency.py
mcp_server/tests/test_spoiler_guard.py
mcp_server/tests/test_master_request.py
backend/tests/test_mcp_error_mapping.py
```

### 14.3 테스트 데이터 원칙

- 실제 방탈출 문제를 사용하지 않는다.
- 가상 테마의 테스트 정답도 로그·스냅샷에 직접 노출하지 않는다.
- 시간 의존 테스트는 현재 시각을 고정한다.
- 각 테스트는 독립 세션과 독립 멱등성 키를 사용한다.
- 실패 테스트 후 저장 상태가 부분 반영되지 않았는지 확인한다.
- 카탈로그 fixture의 checksum을 고정해 변경을 감지한다.

---

## 15. 구현·PR 분리 계획

각 PR은 하나의 논리적 작업만 포함하고 가능한 한 400줄 안팎을 목표로 한다. 이 명세 문서는 상세 계약을 한곳에 고정하는 목적상 예외적으로 길 수 있다.

| 순서 | 브랜치/PR 목적 | 주요 변경 | 선행 조건 |
|---:|---|---|---|
| 1 | 문서 계약 | 본 `mcp-data-contract.md` 합의 | 없음 |
| 2 | 공통 모델 | enum, envelope, error, Pydantic 모델 | PR 1 |
| 3 | 가상 도메인 카탈로그 | Theme/Puzzle/Device/ApprovedHint JSON·검증 | PR 2, 도메인 승인 |
| 4 | 조회 도구 | session, puzzle, history, approved hint | PR 2~3 |
| 5 | 기록 도구 | event, offer 상태 전이, master request | PR 2 |
| 6 | 계약·보안 테스트 | 멱등성, 순서 차단, 정답 비노출 | PR 3~5 |
| 7 | FastAPI 연결 | MCP adapter, 상태·오류 매핑 | MCP 도구 안정화 |
| 8 | Langfuse 관측 | span 속성, 마스킹, 평가 연결 | 도구·FastAPI 연결 |

선행 PR이 병합되지 않은 상태에서 다음 작업이 필요하면 해당 선행 브랜치를 base로 삼고, main 대상 PR에 불필요한 diff가 섞이지 않게 한다.

---

## 16. 역할별 인수 조건

| 담당 | 책임 | 다음 담당자에게 넘길 것 |
|---|---|---|
| 류승민 | 계약 모델, 런타임 데이터, 도구 입출력, 멱등성·무결성 | Pydantic 모델, 도구 스키마, 계약 테스트 |
| 박진형 | 문제·장치·승인 힌트·정상 진행 기준 검수 | 버전 있는 도메인 카탈로그, 승인 기록 |
| 하주성·서문유신 | FastAPI 호출 조정, 외부 요청·응답, MCP 오류 매핑 | adapter, API 통합 테스트, Docker 실행 경로 |
| 심태현 | Langfuse 관측, 평가 판정·점수 | trace 속성, score 규칙, 평가 리포트 |

계약 필드명을 바꾸려면 MCP와 FastAPI 담당자가 함께 검토한다. 승인 힌트의 의미·강도 변경은 도메인 담당 승인 없이 진행하지 않는다. 관측 필드 변경은 평가 담당과 영향 범위를 확인한다.

---

## 17. Definition of Done

다음 조건을 모두 만족해야 MCP 데이터 계약 구현을 완료로 본다.

- [ ] 본 문서의 확정/미확정 항목을 팀이 검토했다.
- [ ] 미확정 설정값이 코드에 설명 없는 숫자로 박혀 있지 않다.
- [ ] 6개 MCP 도구가 Pydantic 입력·출력 모델을 사용한다.
- [ ] 성공·실패 envelope와 오류 코드가 FastAPI 매핑과 일치한다.
- [ ] 승인 힌트가 없는 경우 임의 생성하지 않는다.
- [ ] 미래 문제 요청에서 미래 문제 데이터가 한 필드도 노출되지 않는다.
- [ ] 최종 정답이 유효한 `offer_id`와 명시적 동의 없이는 반환되지 않는다.
- [ ] 최종 정답이 모든 일반 MCP 응답과 Langfuse 로그에서 제외된다.
- [ ] 모든 쓰기 도구가 멱등성 테스트를 통과한다.
- [ ] offer 상태 전이와 동시성 테스트를 통과한다.
- [ ] 직원 호출 성공·중복·저장 실패 테스트를 통과한다.
- [ ] 카탈로그 버전과 checksum이 평가 결과에 기록된다.
- [ ] 관련 단위·계약·통합 테스트 실행 결과를 PR에 남겼다.
- [ ] 팀장과 조원 1명 이상이 PR을 승인한 뒤 사용자가 병합한다.

---

## 18. 팀 검토 체크리스트

### 도메인 담당 확인

- [ ] 약한/강한 힌트의 경계가 모든 문제에서 동일하게 적용되는가?
- [ ] 장치 사용법과 퍼즐 힌트가 분리되어 있는가?
- [ ] `final_answer`가 힌트 문구에 섞이지 않았는가?
- [ ] 정상 진행 기준만으로 완료 여부를 판단할 수 있는가?

### FastAPI 담당 확인

- [ ] 사용자 턴마다 `request_id`를 한 번 생성하는가?
- [ ] ANSWER 명시적 동의가 일회성 `offer_id`에 연결되는가?
- [ ] MCP 오류를 고객용 상태로 안전하게 매핑할 수 있는가?
- [ ] 기록 성공 여부를 확인한 뒤 사용자에게 완료를 알리는가?

### MCP·데이터 담당 확인

- [ ] 모든 조회가 세션과 테마 버전 범위 안에서 수행되는가?
- [ ] 모든 쓰기에 멱등성 키와 트랜잭션이 있는가?
- [ ] 내부 모델과 외부 응답 모델이 분리되어 있는가?
- [ ] 미래 문제와 정답 필드가 allowlist 밖에 있는가?

### 평가·관측 담당 확인

- [ ] `reason_codes`만으로 주요 판정을 집계할 수 있는가?
- [ ] 오류·지연·데이터 버전을 추적할 수 있는가?
- [ ] 힌트·정답 원문 없이도 평가 재현이 가능한가?
- [ ] 정상·경계·실패 케이스가 AC와 연결되는가?
