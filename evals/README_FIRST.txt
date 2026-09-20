FINAL READY CLEAN v2
====================

1) 기존 evals에 이 압축의 파일들을 덮어쓰기
2) API 0회:
   python .\evals\run_model_benchmark.py --check
3) 상세검증(API 0회):
   python .\evals\run_model_benchmark.py --preflight-detail
4) 둘 다 PASS일 때만:
   python .\evals\run_model_benchmark.py --ids 1,9,11,23,26 --eval-name model_compare_5
   RUN

결과는:
  evals\results\model_compare_5\result.csv
  evals\results\model_compare_5\report.txt

같은 평가명으로 재실행하면 두 파일만 갱신됩니다.


최종 비교 - 30문항 전체
======================
먼저:
python .\evals\run_model_benchmark.py --check

PASS 후:
python .\evals\run_model_benchmark.py --eval-name final_compare_30

RUN

결과:
evals\results\final_compare_30\result.csv
evals\results\final_compare_30\report.txt

30문항 × 2모델 = 60회 API 호출.


약점 회귀 테스트
================
먼저:
python .\evals\run_model_benchmark.py --check

PASS 후:
python .\evals\run_model_benchmark.py --ids 4,7,12,13,18,20,21,23,24,27 --eval-name weak_compare_10

RUN

결과:
evals\results\weak_compare_10\result.csv
evals\results\weak_compare_10\report.txt

총 20회 API 호출(10문항 × 2모델).


진짜 마지막 BLIND 12
====================
1) API 0회:
python .\evals\run_model_benchmark.py --check

2) PASS 후:
python .\evals\run_model_benchmark.py --blind-final

3) RUN 입력

호출:
12문항 × 2모델 = 24회

결과:
evals\results\blind_final_12\result.csv
evals\results\blind_final_12\report.txt

판정:
두 모델 모두 model/service 12/12 + critical parity 12/12인 경우에만
토큰과 latency를 비교해 운영 효율을 판단합니다.


Blind50 최종 비교 — 3단계 실행
==============================
목적:
- Core30과 비슷한 category 비율/flow 비율/난이도로 새로운 holdout 50문항 검증
- 정확도/서비스 100%가 우선
- 두 모델이 동등 품질일 때만 토큰/호출시간 비교
- 오답 후 재시도 비용은 절감으로 인정하지 않음

Blind50 전체 비율:
- normal 17 / boundary 20 / failure 13
- HINT_DECISION 25
- Core30의 나머지 route를 비슷한 비율로 분산
- stage1은 11개 route를 모두 포함

정책/서비스 코드 동결:
- runtime_policy.json
- skill_policy.py
- tool_policy.py
- hard_guard.py
- benchmark_models.json
- static prompt hash
Blind50 실행 전 자동 hash 검증.

0) API 0회 사전검증
python .\evals\run_model_benchmark.py --check

반드시 아래가 보여야 함:
- PREFLIGHT GATE: PASS
- 50-case Blind contract: 50/50
- Blind50 freeze: PASS

1) Stage 1: 16문항 × 2모델 = 32회
python .\evals\run_model_benchmark.py --blind50-stage 1
RUN

2) Stage 2: 17문항 × 2모델 = 34회
python .\evals\run_model_benchmark.py --blind50-stage 2
RUN

3) Stage 3: 17문항 × 2모델 = 34회
python .\evals\run_model_benchmark.py --blind50-stage 3
RUN

모든 stage 완료 후 API 0회 병합:
python .\evals\run_model_benchmark.py --blind50-merge

최종 결과:
evals\results\blind50_final\result.csv
evals\results\blind50_final\report.txt

판정 원칙:
1. MODEL GATE 100%
2. SERVICE GATE 100%
3. critical output parity 100%
4. 위 3개가 모두 만족될 때만 토큰/latency 비교
5. 정확도 차이가 있으면 토큰이 적은 모델을 우선하지 않음
