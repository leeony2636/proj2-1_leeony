# STT 5개 모델 비교 및 최종 모델 선정 보고서

## 1. 목적

방탈출 Agent의 STT 입력 모델을 선정하기 위해 먼저 **5개 후보를 동일한 고정 hold30**으로 비교했고, 그 결과에서 **Whisper Large-v3-Turbo Base와 Whisper Small**을 후속 후보로 남겼다. 이후 두 모델에 방탈출 도메인 Adapter를 적용해 다시 동일한 고정 30개 음성으로 비교했다.

최종 선정 모델은 **openai/whisper-large-v3-turbo + Escape-room Adapter, Epoch 2**이다.

---

## 2. 동일 테스트 조건

- 평가셋: **고정 30개 음성**
- 구성: **3화자(Hyunbin / Anna Kim / Michael) × 동일 10문장**
- 주요 평가 지표: WER, CER, Exact Match, Keyword Accuracy, Filler Accuracy, Latency, RTF
- 1차 비교에서 Whisper 계열은 4bit, Korean Wav2Vec2 XLS-R은 FP32 기록
- 최종 Small/Large 비교는 동일 fixed_test 30개, 동일 정규화 방식, 동일 Korean transcribe 조건을 사용
- WER/CER는 동일 기준으로 계산했고, 숫자 치환이나 임의 단어 치환은 하지 않음
- 지연시간은 해당 실행에서 실제 측정된 값이며, 하드웨어/세션 조건이 별도 파일에 완전히 기록되어 있지 않으므로 절대적인 모델 속도 일반화보다는 **이번 실험 관측값**으로 해석

---

## 3. 1차: 5개 모델 비교

| 후보 | Corpus WER | Corpus CER | Exact Match | Keyword | Filler | 평균 지연 | 평균 RTF | 1차 판단 |
|---|---:|---:|---:|---:|---:|---:|---:|---|
| Whisper Large-v3-Turbo Base | 10.26% | 3.40% | 21/30 (70.00%) | 78.33% | 63.33% | 0.428s | 0.111 | 후속 후보 |
| ChefEar Adapter | 20.00% | 3.17% | 14/30 (46.67%) | 78.33% | 50.00% | 0.452s | 0.117 | 1차 제외 |
| Whisper Small | 13.33% | 3.17% | 20/30 (66.67%) | 75.00% | 86.67% | 0.738s | 0.183 | 후속 후보 |
| Whisper Medium | 20.51% | 4.08% | 13/30 (43.33%) | 75.00% | 73.33% | 0.776s | 0.201 | 1차 제외 |
| Korean Wav2Vec2 XLS-R | 57.44% | 26.53% | 0/30 (0.00%) | 28.33% | 33.33% | 0.067s | 0.017 | 1차 제외 |

### 1차 판단

**Whisper Large-v3-Turbo Base**
- Corpus WER **10.26%**로 5개 중 가장 낮음
- Exact Match **21/30, 70.00%**
- Keyword Accuracy **78.33%**
- 정확도 중심 후속 후보로 유지

**Whisper Small**
- Corpus WER **13.33%**
- CER **3.17%**
- Exact Match **20/30, 66.67%**
- Filler Accuracy **86.67%**로 5개 중 가장 높음
- 경량 후보로 후속 도메인 학습 진행

**1차 제외**
- ChefEar Adapter: WER 20.00%, Exact Match 46.67%. 요리 도메인 Adapter가 방탈출에서 일관된 향상을 보이지 않음.
- Whisper Medium: WER 20.51%, Exact Match 43.33%. Small보다 큰 모델이지만 이번 hold30에서 정확도 이점 없음.
- Korean Wav2Vec2 XLS-R: WER 57.44%, CER 26.53%, Exact Match 0%, Keyword 28.33%. 속도는 빠르지만 전사 품질이 Agent 입력으로 부족함.

---

## 4. 도메인 학습 후 비교에 사용한 Epoch

### Small 학습 기록

| Epoch | Train Loss | Eval Loss | Val WER | Val CER | Val Exact |
|---:|---:|---:|---:|---:|---:|
| 1 | 기록 없음 | 0.6554 | 9.22% | 2.19% | 61.11% | **← 고정30에 사용**
| 2 | 기록 없음 | 0.4571 | 8.87% | 2.47% | 61.11% |
| 3 | 4.039645724826389 | 0.6790 | 10.99% | 5.34% | 66.67% |
| 4 | 16.76186286078559 | 12.3776 | 102.84% | 104.79% | 0.00% |
| 5 | 46.33667331271701 | 10.8340 | 100.00% | 100.00% | 0.00% |
| 6 | 41.788479275173614 | 10.3437 | 100.00% | 100.00% | 0.00% |

- 최종 고정30 비교에는 **이전 실험에서 확정해 둔 Small Epoch 1 결과**를 사용했다.
- `small_epoch_metrics.csv`의 validation 기록과 고정30 결과는 서로 다른 평가 단계이므로 혼동하지 않는다.
- Small Epoch 1의 train loss는 제공된 CSV에 기록되어 있지 않다.

### Large 학습 기록

| Epoch | Train Loss | Eval Loss | Val WER | Val CER | Val Exact |
|---:|---:|---:|---:|---:|---:|
| 1 | 3.5313 | 0.1084 | 3.90% | 0.96% | 80.56% |
| 2 | 0.2488 | 0.0465 | 4.26% | 0.68% | 80.56% | **← 선택 Epoch**
| 3 | 0.1027 | 0.0496 | 4.26% | 0.82% | 83.33% |
| 4 | 0.0630 | 0.0489 | 4.96% | 0.82% | 80.56% |
| 5 | 0.0423 | 0.0496 | 3.55% | 0.82% | 83.33% |
| 6 | 0.0300 | 0.0501 | 3.55% | 0.82% | 83.33% |

- Large는 **Epoch 2**를 고정30 비교 체크포인트로 사용했다.
- Epoch 2 validation: Train Loss **0.2488**, Eval Loss **0.0465**, Val WER **4.26%**, Val CER **0.68%**, Val Exact **80.56%**.

---

## 5. 최종: Small Epoch 1 vs Large Epoch 2 동일 고정30 비교

| 지표 | Small + Escape Adapter Epoch 1 | Large-v3-Turbo + Escape Adapter Epoch 2 | 차이 |
|---|---:|---:|---:|
| Corpus WER | 20.00% | **6.15%** | Large가 69.2% 상대 감소 |
| Corpus CER | 3.17% | **1.36%** | Large가 57.1% 상대 감소 |
| Exact Match | 14/30 (46.67%) | **23/30 (76.67%)** | +9문장 |
| Keyword Accuracy | 78.33% | **85.56%** | +7.22%p |
| Filler Accuracy | 50.00% | **100.00%** | +50.00%p |
| 평균 Latency | 0.452s | **0.281s** | 이번 실행에서 37.8% 감소 |
| 평균 RTF | 0.1174 | **0.0736** | Large가 더 낮음 |

### 문장 단위 WER 변화

- Large가 Small보다 개선: **12/30**
- 동일: **15/30**
- Large가 수치상 악화: **3/30**
- 악화 ID: **H_F03, A_F03, M_F03**

세 악화 문장은 모두 F03 계열이며, Large 출력의 `말해줄래요` → `말해 줄래요` 띄어쓰기 차이로 WER이 올라갔다. 세 문장의 Large CER는 모두 0.0이므로 문자 내용 자체는 동일했다.

### 화자별 결과

| 화자 | Small 평균 WER | Large 평균 WER | Small 평균 CER | Large 평균 CER | Small Exact | Large Exact |
|---|---:|---:|---:|---:|---:|---:|
| Hyunbin | 23.88% | 3.93% | 2.78% | 0.77% | 4/10 | 8/10 |
| Anna Kim | 19.70% | 7.26% | 4.14% | 1.88% | 4/10 | 7/10 |
| Michael | 17.02% | 5.83% | 2.78% | 1.11% | 6/10 | 8/10 |

---

## 6. 최종 선정 모델

### **선정: openai/whisper-large-v3-turbo + Escape-room Adapter / Epoch 2**

선정 이유는 다음과 같다.

1. 같은 고정30에서 Corpus WER이 **20.00% → 6.15%**로 감소했다.
2. Corpus CER이 **3.17% → 1.36%**로 감소했다.
3. Exact Match가 **14/30 → 23/30**으로 증가했다.
4. Keyword Accuracy가 **78.33% → 85.56%**로 향상됐다.
5. Filler Accuracy가 **50.00% → 100.00%**로 향상됐다.
6. 이번 실행에서는 평균 latency와 RTF도 Small보다 낮게 측정됐다.
7. WER이 나빠진 3문장은 모두 띄어쓰기 차이였고 CER는 0이어서, 실제 문장 내용 인식 저하로 보기 어렵다.

따라서 **방탈출 사용자의 발화를 Agent 입력으로 넘기는 정확성, 핵심어 보존, 습관 발화 보존을 함께 고려했을 때 Large Epoch 2를 현재 최종 STT 모델로 선정**한다.

---

## 7. 학습/모델 파라미터 기록

### 확인된 사항

| 항목 | Small | Large |
|---|---|---|
| Base Model | `openai/whisper-small` | `openai/whisper-large-v3-turbo` |
| 도메인 학습 결과 | Escape-room PEFT Adapter | Escape-room PEFT Adapter |
| 고정30 사용 Epoch | 1 | 2 |
| 평가 체크포인트 | Epoch1 / checkpoint-36 | Epoch2 / checkpoint-72 사용 비교 흐름 |
| 평가 Base 양자화 | 4bit NF4 | 4bit NF4 |
| 4bit compute dtype | float16 | float16 |
| double quant | 사용 | 사용 |
| 언어/Task | Korean / transcribe | Korean / transcribe |
| 최대 생성 토큰 | 128 | 128 |
| 선택 Epoch Train Loss | 제공 CSV에 없음 | 0.2488 |
| 선택 Epoch Eval Loss | 0.6554 | 0.0465 |
| 선택 Epoch Val WER | 9.22% | 4.26% |
| 선택 Epoch Val CER | 2.19% | 0.68% |
| 선택 Epoch Val Exact | 61.11% | 80.56% |

### 제공 자료만으로 확인할 수 없는 항목

다음 값은 현재 제공된 CSV/ZIP/평가 코드에 없어서 임의로 만들지 않았다.

- 정확한 **trainable parameter count**
- LoRA/QLoRA의 **r**
- `lora_alpha`
- `lora_dropout`
- 정확한 `target_modules`
- optimizer / learning rate / batch size / gradient accumulation 등 전체 학습 설정

이 값들은 실제 학습 스크립트 또는 `adapter_config.json`/Trainer 설정 파일이 있으면 정확히 추가할 수 있다.

---

## 8. 최종 흐름 요약

**5개 후보 동일 hold30 비교**
→ Large-v3-Turbo Base + Small Base 2개 유지
→ 방탈출 도메인 Adapter 학습
→ Small Epoch1 / Large Epoch2 선정
→ 동일 고정30 재평가
→ **Large-v3-Turbo + Escape-room Adapter Epoch2 최종 선정**

---

## 9. 근거 파일

- `stt_model_eval_v1.zip`
  - `model_comparison_all_summary.csv`
  - `model_comparison_all.csv`
  - `MODEL_SELECTION_NOTE.txt`
  - 개별 5모델 hold30 결과
- `small_epoch_metrics(1).csv`
- `large_epoch_metrics(1).csv`
- `adapter_hold30_results(1).csv`
- `large_epoch2_hold30_results(1).csv`
- `small_epoch1_vs_large_epoch2_hold30_comparison(1).csv`
- `small_epoch1_vs_large_epoch2_hold30_summary(1).csv`
