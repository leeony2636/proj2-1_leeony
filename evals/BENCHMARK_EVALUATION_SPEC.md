# Evaluation Specification

```text
방탈출 Agent 모델 비교 - FINAL READY v2
=======================================

핵심 구조
---------
LLM:
- route
- intent/emotion
- needs_clarification
- direct_answer_request
- frustration_high
만 구조화한다.

SkillPolicy:
- ANSWER_REQUEST
- RE_REQUEST_OVERRIDE
- EMOTION_OVERRIDE
- BASE_RULE_TIME_AND_PROGRESS
- BASE_RULE_DEFAULT
를 코드로 계산한다.
최종 weak/strong도 코드가 결정한다.

HardGuard:
명확한 위험/예외를 모델보다 먼저 보호한다.

ToolPolicy:
effective route + 현재 state로 필요한 MCP Tool만 결정한다.

금지
----
- RAG
- 벡터 검색
- 질문별 Skill retrieval
- full SKILL.md 매호출 전송
- 모델의 Tool 선택
- 모델의 최종 Skill rule/weak/strong 결정
- expected/question_id/category의 runtime 전달

route 경계 보완
---------------
EQUIPMENT_FAULT:
'이미 열려 있다/이미 풀려 있다/작동하지 않는다'처럼
자물쇠·소품·장치 자체 상태가 이상한 경우.
'왜 안 열려요?'처럼 원인 불명이어도 이 route에서 clarification.

PROGRESS_VERIFICATION:
'5분 만에 전부 풀었다'처럼 사용자 완료/진도 주장 자체가
비정상인지 검증하는 경우.
물리 객체 상태 이상과 구분한다.

결과 저장
---------
앞으로 results 루트에 timestamp 파일을 계속 만들지 않는다.

예:
evals/results/
└─ eval_05_ids_1-9-11-23-26/
   ├─ result.csv
   └─ report.txt

같은 평가를 다시 실행하면 그 폴더의 두 파일만 갱신된다.

원하는 이름:
python .\evals\run_model_benchmark.py --ids 1,9,11,23,26 --eval-name model_compare_5

사전검증
--------
python .\evals\run_model_benchmark.py --check
python .\evals\run_model_benchmark.py --preflight-detail

모두 PASS 후에만 API 테스트.

합격
----
model_case_pass:
route + 모델 boolean signal + schema

skill_policy_pass:
Skill.md 규칙의 결정론 계산

tool_policy_pass:
MCP Tool 결정론 계산

service_case_pass:
schema valid + HardGuard가 반영된 effective route + SkillPolicy + ToolPolicy가 모두 통과.
MODEL GATE와 SERVICE GATE는 별도 진단이며, Guard가 서비스 경로를 보호한 경우 model_case_pass가 0이어도 service_case_pass는 1일 수 있다.

선택된 평가 문항 전체가 100%일 때만 ACCEPT.


FINAL CLEAN 구조 보완
--------------------
모델:
- route / intent / emotion / needs_clarification /
  direct_answer_request / frustration_high /
  emotion_override_qualified만 구조화
- Tool 이름과 최종 hint rule/strength는 출력하지 않음

SkillPolicy:
- 정답 직접 요구
- 재요청 승격
- 감정 오버라이드
- 15분/남은문제비율 50% 규칙
- 기본 약한 힌트
를 deterministic code로 결정

감정 오버라이드:
- frustration_high 자체만으로 발동하지 않음
- emotion_override_qualified=true일 때만 발동
- true 조건은 시간/반복시도 언급 + 무력감이 함께 있는 경우

Route 경계:
- '이미 풀림/이미 열림/고장/작동 안 함' = EQUIPMENT_FAULT
- 불가능한 진행 주장 = PROGRESS_VERIFICATION
- 원인/진도 위치 모호 = PROGRESS_ESTIMATION/확인
- 미래 문제 = SPOILER_BLOCK
- 다른 테마 = THEME_ISOLATION
- 정답 보호우회 = ANSWER_EXPOSURE_BYPASS

결과 저장:
evals/results/<run_id>_ids_<문항ID>/
    result.csv
    report.txt

평가 1회당 폴더 하나, CSV 1개 + TXT 1개만 생성한다.


FINAL 30문항 비교
----------------
최종 비교는 일부 표본이 아니라 고정 평가셋 30문항 전체를 사용한다.

구성:
- normal 10
- boundary 12
- failure 8

최종 보고서에는 모델별로:
- MODEL GATE
- SERVICE GATE
- category별 model/service 통과수
- model failed ids
- service failed ids
를 별도로 출력한다.

MODEL GATE:
model_case_pass 30/30일 때만 ACCEPT.

SERVICE GATE:
service_case_pass 30/30일 때만 ACCEPT.

실행:
python .\evals\run_model_benchmark.py --eval-name final_compare_30

RUN

총 호출:
30문항 × 2모델 = 60 logical API calls.
retry/fallback 없음.


약점 회귀 테스트 10문항
----------------------
30문항 최종 비교에서 두 후보 모델 중 하나라도 model_case_pass에 실패한 문항의 합집합:

4, 7, 12, 13, 18, 20, 21, 23, 24, 27

이 10문항은 새 정답을 만든 것이 아니라 기존 고정 30문항의 부분집합이다.
dataset / expected / category / scoring은 변경하지 않는다.

이번 보완은 일반화된 경계 규칙만 compact policy에 추가:
- 일반 정답요구 vs 정답보호 우회
- 장비 조작법 vs 입력 위치
- 현재 퍼즐이 이미 알려진 경우 불필요한 clarification 방지
- 원인 미확인 장비 문제 vs 명백한 물리 이상
- 부분완료 vs 진행 검증
- 구조화된 진행 검증 정보가 있을 때 불필요한 사용자 확인 방지

실행:
python .\evals\run_model_benchmark.py --ids 4,7,12,13,18,20,21,23,24,27 --eval-name weak_compare_10

총 10문항 × 2모델 = 20 API 호출.
이 결과는 '약점 회귀 회복 여부'를 보는 테스트이며,
전체 일반화 성능의 근거는 직전 30문항 결과와 함께 해석한다.


BLIND FINAL 12 — 동등품질이면 효율 선택
-------------------------------------
목적:
1) 이전 약점이 새로운 표현에서도 일반화되는지 확인
2) 정책/프롬프트/코드만으로 5.4와 5.6이 동일한 핵심 판단을 내리는지 확인
3) 품질이 동일하면 total token + API latency가 더 낮은 쪽의 운영 효율 확인

중요:
- 기존 30문항/약점 10문항의 문장을 재사용하지 않음
- 기존 runtime_policy / SkillPolicy / ToolPolicy / HardGuard는 이 blind set을 만든 뒤 수정하지 않음
- blind expected는 모델에게 전달되지 않음
- 실제 비용은 cached/uncached pricing을 여기서 가정하지 않음

Blind 12:
- ids 101~112
- direct answer vs bypass
- equipment usage vs input location
- ambiguous vs explicit equipment fault
- known-puzzle clarification
- strong tone vs true emotion override
- partial completion vs progress verification
- re-request + history reuse

최종 판단 순서:
A. 두 모델 모두 MODEL GATE 12/12
B. 두 모델 모두 SERVICE GATE 12/12
C. critical output parity 12/12
D. A~C가 모두 충족될 때만 효율 비교

효율:
- total tokens
- uncached prompt tokens
- completion + reasoning tokens
- average latency
- p95 latency

실행:
python .\evals\run_model_benchmark.py --blind-final

RUN

결과:
evals\results\blind_final_12\result.csv
evals\results\blind_final_12\report.txt


BLIND50 V1 — 최종 일반화/효율 검증
----------------------------------
Core30 비율:
- normal 10/30 = 33.3%
- boundary 12/30 = 40.0%
- failure 8/30 = 26.7%

Blind50 비율:
- normal 17/50 = 34.0%
- boundary 20/50 = 40.0%
- failure 13/50 = 26.0%

Flow 분포:
- HINT_DECISION 25
- PROGRESS_TRANSITION 3
- EQUIPMENT_FAULT 3
- PROGRESS_ESTIMATION 3
- SPOILER_BLOCK 3
- ANSWER_EXPOSURE_BYPASS 3
- INPUT_LOCATION 2
- EQUIPMENT_USAGE 2
- MASTER_REQUEST 2
- PROGRESS_VERIFICATION 2
- THEME_ISOLATION 2

실행은 16 + 17 + 17로 분리한다.
Stage1은 11개 route를 모두 포함해 조기 차이 탐지력이 높도록 구성한다.
Stage2/3는 남은 새로운 표현과 상태 조합으로 일반화를 확장한다.

중요:
- 50문항의 expected는 실행 전에 고정됨.
- 모델 호출에는 expected/category/question_id를 전달하지 않음.
- Blind50 생성 후 runtime policy / SkillPolicy / ToolPolicy / HardGuard / 후보 모델 config / static prompt를 동결.
- hash가 달라지면 Blind50 실행을 중단.
- SDK retry=0, fallback 없음.
- 같은 품질이 아닐 경우 효율 비교는 DEFER.
- 오답 1회 + 정답 재호출이 생기면 두 호출의 토큰/시간이 실제 운영비용이다.

최종 병합은 API 0회:
python .\evals\run_model_benchmark.py --blind50-merge

```
