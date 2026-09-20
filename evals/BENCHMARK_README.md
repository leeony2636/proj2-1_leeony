# Escape Room Agent Model Benchmark Base

방탈출 Agent에서 **모델 해석능력 + 결정론 Skill/Tool 정책 + 최종 서비스 품질 + 토큰/지연시간**을 분리해 비교하기 위한 재사용 가능한 벤치마크 베이스입니다.

## 핵심 원칙

정확도를 희생해 토큰을 아끼지 않습니다. **SERVICE GATE 100%가 우선**이고, MODEL GATE는 모델의 route/intent/signal 해석능력을 별도로 진단합니다. 효율 비교는 최소 2개 모델이 `model+service 100%`이고 critical output parity도 100%일 때만 수행합니다. 오답 후 재호출이 필요하면 첫 오답 호출 토큰/시간도 실제 비용으로 봅니다.

## 기준 구조

- LLM: `route`, `intent`, `emotion`, `needs_clarification`, `direct_answer_request`, `frustration_high`, `emotion_override_qualified` 구조화
- HardGuard: 명확한 위험/예외를 fail-closed 보호
- SkillPolicy: weak/strong, 정답요구, 재요청, 감정오버라이드 등을 코드로 결정
- ToolPolicy: effective route + state로 MCP Tool을 결정
- 모델은 Tool 이름이나 최종 hint strength를 직접 선택하지 않음

## 데이터셋

- Core30: normal 10 / boundary 12 / failure 8
- Blind12: 약점 보완 후 처음 보는 표현 holdout
- Blind50: normal 17 / boundary 20 / failure 13, 16+17+17 stage 실행

Blind 데이터는 결과를 본 뒤 수정하지 않습니다. 정책/프롬프트를 바꾸면 새 blind 버전을 만들어야 합니다.


## 이 저장소에서 고정하는 기준

- **Core30 (`evals/dataset.jsonl`)**: 팀/개인 프로젝트의 기준 회귀셋입니다. normal 10 / boundary 12 / failure 8 구성은 기준선으로 유지합니다. 정책이나 채점 계약을 바꾸면 새 버전으로 분리하고 기존 Core30 결과를 덮어쓰지 않습니다.
- **Blind50 (`evals/dataset_blind50.jsonl`)**: 새 모델을 같은 조건에서 비교하는 고정 비교군입니다. normal 17 / boundary 20 / failure 13이며, 모델 목록만 교체할 수 있고 데이터/정책/프롬프트/SkillPolicy/ToolPolicy/HardGuard는 manifest hash로 동결합니다.
- **Benchmark logic (`evals/*.py`)**: 모델이 바뀌어도 동일한 route/model/skill/tool/service/token/latency 분석을 수행하는 재사용 베이스입니다.
- **Team project 적용**: 이 저장소 자체가 팀 저장소를 수정하지는 않습니다. 팀 프로젝트에는 `evals/`와 실제 서비스에 필요한 정책 코드만 선택적으로 반영합니다. 자세한 범위는 `TEAM_INTEGRATION.md`를 따릅니다.

## 프로젝트에 넣는 위치

이 저장소의 `evals/` 폴더를 실제 방탈출 프로젝트 루트에 둡니다. 벤치마크는 아래 프로젝트 파일을 읽습니다.

```text
project_root/
├─ backend/services/llm.py      # SYSTEM_PROMPT
├─ skills/SKILL.md
├─ mcp_server/server.py         # 실제 FastMCP 등록 확인
└─ evals/                       # 이 벤치마크
```

## 모델 추가/교체

`evals/benchmark_models.json`의 `models` 배열에 원하는 OpenAI 모델을 1개 이상 넣습니다. 모델 개수는 고정되어 있지 않습니다.

```json
{
  "models": [
    {
      "name": "candidate_a",
      "provider": "openai",
      "model": "YOUR_MODEL_ID_A",
      "send_temperature": true,
      "temperature": 1,
      "max_completion_tokens": 650,
      "timeout_seconds": 60
    },
    {
      "name": "candidate_b",
      "provider": "openai",
      "model": "YOUR_MODEL_ID_B",
      "send_temperature": false,
      "max_completion_tokens": 650,
      "timeout_seconds": 60
    }
  ]
}
```

`send_temperature=false`는 temperature 파라미터를 받지 않는 모델에 사용할 수 있습니다. 현재 기본 베이스의 API adapter는 OpenAI API 모델을 대상으로 합니다.

## 실행

```powershell
python .\evals\run_model_benchmark.py --check
```

반드시 preflight와 Blind50 freeze가 PASS여야 합니다.

Core30:

```powershell
python .\evals\run_model_benchmark.py --eval-name core30_compare --max-api-calls 250
```

Blind50 단계별:

```powershell
python .\evals\run_model_benchmark.py --blind50-stage 1 --max-api-calls 250
python .\evals\run_model_benchmark.py --blind50-stage 2 --max-api-calls 250
python .\evals\run_model_benchmark.py --blind50-stage 3 --max-api-calls 250
python .\evals\run_model_benchmark.py --blind50-merge
```

각 실제 API 실행은 `RUN`을 입력해야 시작됩니다. SDK retry는 0이고 fallback은 없습니다.

## 자동 분석

각 모델마다 아래를 동일하게 계산합니다.

- route pass
- model_case_pass
- deterministic SkillPolicy pass
- deterministic ToolPolicy pass
- service_case_pass
- normal / boundary / failure 별 model/service 통과수
- model/service 실패 question id
- prompt / cached / uncached / completion / reasoning / total tokens
- 평균 / median / p95 latency
- MODEL GATE / SERVICE GATE

2개 이상의 모델을 넣으면 all-model critical output parity도 계산합니다. strict quality-qualified 후보가 2개 이상이고 parity도 100%일 때만 efficiency lead를 계산합니다.

## 현재 reference 결과

동결된 Blind50에서:

- GPT-5.4 mini: route 46/50, model 42/50, Skill 49/50, Tool 48/50, **service 46/50**
- GPT-5.6 Luna: route 49/50, model 44/50, Skill 50/50, Tool 50/50, **service 50/50**

따라서 이 reference 실행에서는 품질이 동일하지 않아 효율 비교는 선택 기준으로 사용하지 않았습니다. 상세 원본은 `reference_results/blind50_final/`에 있습니다.

## 테스트 이력

`history/benchmark_history_complete.csv`와 `.txt`에는 1문항 초기 테스트부터 Blind50까지의 사용 가능한 결과를 통합했습니다. 과거 버전은 계약이 다르므로 `comparison_group`이 같은 결과끼리 직접 비교하세요.

## 제한사항

이 벤치마크는 방탈출 Agent 도메인에서의 모델/서비스 적합성을 측정합니다. 모델의 범용 성능 전체를 대표하지 않습니다. 또한 Tool 선택 계획까지는 검증하지만 실제 MCP 함수 실행, DB 응답, 네트워크 장애 복구는 별도 E2E 테스트가 필요합니다.
