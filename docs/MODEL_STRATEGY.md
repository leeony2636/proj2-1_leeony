# Multi-LLM Model Strategy — 초안

## 목적

모델 이름을 먼저 확정하기보다, 동일한 Agent 계약에서 여러 Provider를 비교해
**Tool 선택 안정성·구조화 출력·지연·비용**을 측정한 뒤 주 모델을 선택합니다.

## 사용 가능한 Provider 후보

1. OpenAI API — 보유한 API 크레딧으로 개발/평가 가능
2. Google Cloud Vertex AI — GCP 무료 크레딧 활용 후보
3. Microsoft Foundry / Azure OpenAI — Azure 무료 크레딧 활용 후보

현재 문서에는 특정 모델의 성능 우열을 결과처럼 적지 않습니다.
실제 콘솔에서 사용 가능한 소형 Tool Calling 모델을 확인한 뒤 모델명을 확정합니다.

## STT 전략

STT는 LLM과 별도의 입력 계층으로 평가합니다. 2026-09-22 고정 30문장 비교에서는 **Whisper Large-v3-Turbo + Escape-room Adapter / Epoch 2**가 현재 STT 후보로 선정되었습니다.

동일 hold30에서 Small Epoch 1 대비 Large Epoch 2는 Corpus WER **20.00% → 6.15%**, Corpus CER **3.17% → 1.36%**, Exact Match **14/30 → 23/30**으로 기록되었습니다. 세부 근거는 `docs/stt/STT_MODEL_SELECTION_REPORT.md`와 CSV에 보관합니다.

다만 현재 서비스 코드는 여전히 `MockSTTAdapter`를 사용합니다. 최종 Large Epoch 2 Adapter를 Python 3.13 프로젝트 환경에서 로드하고 실제 WAV를 전사하는 Compatibility Gate 2는 아직 통과하지 않았으므로, **모델 선정 완료와 서비스 통합 완료를 구분**합니다.

STT의 출력은 `transcript`, `confidence`, `language`, `duration_ms`를 갖는 내부 결과로 정규화하고, Agent에는 검증된 `transcript`만 `message`로 전달합니다. `confidence`가 기준 미만이거나 전사가 비어 있으면 LLM 호출과 힌트 판정을 하지 않고 다시 말하기를 요청합니다.

## LLM 개입 범위

LLM:
- 고객 자연어 의도 파악
- 감정 신호 구조화
- 추가 정보 필요 여부 판단
- 필요한 MCP Tool 선택
- 승인된 결과를 사용자 언어로 표현

STT:
- 제출된 음성의 텍스트 변환
- 언어·신뢰도·길이 메타데이터 반환
- 의도·감정·힌트 강도·정답 판단 금지

LLM이 하지 않는 것:
- WEAK/NORMAL/STRONG 최종 결정
- 승인되지 않은 힌트 생성
- AnswerVault 직접 조회
- 장비 이상을 임의 해결했다고 판단
- STT 결과를 임의로 보정하거나 음성 원문을 로그에 남기는 것

## 개발/평가 모드

```text
같은 평가 입력
   ├─ OpenAI 후보
   ├─ Vertex AI 후보
   └─ Azure 후보
        ↓
같은 Structured Output
같은 MCP Tool
같은 hint_decision.py
        ↓
Langfuse 비교
```

비교 항목:
- intent 정확성
- Tool 선택
- Structured Output 계약 준수
- latency
- token / cost
- timeout / retry / fallback

## 발표/서비스 모드

평가 결과가 나온 뒤:
- 가장 안정적인 Provider를 `PRIMARY`
- 다른 Provider를 `FALLBACK`
으로 설정합니다.

테스트 전에는 Primary 순위를 확정하지 않습니다.
