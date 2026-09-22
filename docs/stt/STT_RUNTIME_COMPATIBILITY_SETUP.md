# STT 런타임 호환성·버전 충돌 방지 가이드

## 1. 목적

이 문서는 방탈출 **2차 프로젝트에서 STT 모델을 실제 파이프라인에 연결할 때**
Python 버전, CUDA, PyTorch, Transformers, PEFT 등에서 발생할 수 있는
버전 충돌을 줄이기 위한 **실행환경 기준 문서**다.

기존의 다음 3개 기록을 하나로 통합했다.

- `STT_COMPATIBILITY_TEST.md`
- `STT_GPU_ENVIRONMENT.txt`
- `STT_PY313_PACKAGES.txt`

중요한 운영 원칙은 다음과 같다.

> **STT 학습 환경(Python 3.11)과 2차 프로젝트 실행 환경(Python 3.13)을 분리한다.**

현재 프로젝트의 최종 STT 후보는
**Whisper Large-v3-Turbo + Escape-room Adapter / Epoch 2**이므로,
최종 통합 전에는 반드시 이 모델 조합으로 별도 Compatibility Gate를 통과해야 한다.

---

## 2. 현재 확인된 환경

| 항목 | 확인 값 |
|---|---|
| OS | Windows |
| GPU | NVIDIA GeForce RTX 4060 |
| VRAM | 8 GB / NVIDIA-SMI 표시 8188 MiB |
| NVIDIA Driver | 552.22 |
| NVIDIA-SMI CUDA Version | 12.4 |
| 프로젝트 Python | 3.13.14 |
| Python 3.13 테스트 가상환경 | `Z:\escape\stt_runtime\venv\project313_stt_test` |
| 학습 Python | 3.11 계열, 별도 환경 유지 |
| 검증 모델 | `openai/whisper-small` |
| Framework | PyTorch + Transformers |
| GPU 방식 | CUDA |

---

## 3. Compatibility Gate 현황

### Gate 1 — PASS

Python 3.13.14 환경에서 `openai/whisper-small` Base 모델에 대해 다음 항목이 실제로 확인됐다.

- PyTorch 실행
- CUDA GPU 사용
- Hugging Face Transformers 사용
- Whisper Small 다운로드
- Whisper Small 가중치 로딩
- CUDA GPU 모델 로딩

실제 기록:

```text
WHISPER SMALL CUDA LOAD PASS
```

### Gate 1이 의미하는 범위

Gate 1은 **Python 3.13에서 Whisper 계열 Base 모델을 CUDA로 로드할 수 있다는 기반 확인**이다.

다만 이것만으로 아래 항목까지 검증됐다고 보면 안 된다.

- Python 3.11에서 학습한 PEFT Adapter를 Python 3.13에서 로드
- 최종 선택 모델인 Whisper Large-v3-Turbo + Escape-room Adapter 로드
- 실제 WAV 추론
- 2차 프로젝트 전체 dependency와 함께 실행
- FastAPI/MCP/Agent 등 다른 패키지와의 충돌 여부

---

## 4. 최종 프로젝트용 Compatibility Gate 2

기존 문서의 Gate 2는 Whisper Small을 대상으로 작성됐지만,
현재 모델 선정이 완료됐으므로 **실제 Gate 2 대상은 최종 모델로 바꿔서 검증한다.**

### 대상

- Base: `openai/whisper-large-v3-turbo`
- Adapter: Escape-room Adapter
- 선택 Epoch: **Epoch 2**
- 체크포인트: **checkpoint-72**
- 학습 환경: Python 3.11
- 서비스/프로젝트 환경: Python 3.13.14

### 반드시 확인할 항목

1. Python 3.11 학습 결과의 `adapter_model.safetensors` 존재 확인
2. `adapter_config.json` 존재 확인
3. Python 3.13에서 PEFT Adapter 로딩
4. Whisper Large-v3-Turbo Base + Adapter 결합
5. CUDA GPU 로딩
6. 실제 WAV 1개 전사
7. 고정 테스트 WAV 일부 전사
8. 2차 프로젝트 전체 패키지와 함께 import
9. STT 호출 후 Agent 파이프라인까지 연결
10. dependency 충돌 / DLL 오류 / CUDA 오류 없는지 확인

### Gate 2 통과 기준

아래가 모두 성공해야 2차 프로젝트의 STT 런타임으로 확정한다.

```text
[ ] Base model load
[ ] PEFT adapter load
[ ] CUDA load
[ ] WAV transcription
[ ] Korean transcription
[ ] Project dependency import
[ ] Agent pipeline call
[ ] No dependency/version conflict
```

---

## 5. Python 3.13에서 확인된 핵심 패키지 버전

아래 버전은 실제 테스트 환경에서 기록된 값이다.

| 패키지 | 버전 |
|---|---|
| Python | 3.13.14 |
| torch | 2.6.0+cu124 |
| torchaudio | 2.6.0+cu124 |
| torchvision | 0.21.0+cu124 |
| transformers | 5.17.0 |
| peft | 0.21.0 |
| accelerate | 1.15.0 |
| tokenizers | 0.23.2 |
| safetensors | 0.8.0 |
| huggingface_hub | 1.32.0 |
| librosa | 1.0.0 |
| soundfile | 0.14.0 |
| numpy | 2.5.2 |
| scipy | 1.18.1 |
| numba | 0.67.0 |
| sentencepiece | 0.2.2 |
| scikit-learn | 1.9.1 |

### 중요한 해석

이 표는 **현재 Python 3.13 테스트 환경에서 실제 설치돼 있던 버전 기록**이다.

따라서 2차 프로젝트에서 STT를 붙일 때 처음부터 최신 버전으로 다시 올리는 것보다,
**우선 이 검증된 조합을 기준점으로 잡고 필요한 패키지만 추가하는 방식**이 안전하다.

---

## 6. GPU/CUDA 기준

실제 `nvidia-smi` 기록:

```text
NVIDIA-SMI 552.22
Driver Version: 552.22
CUDA Version: 12.4
GPU: NVIDIA GeForce RTX 4060
VRAM: 8188 MiB
```

테스트 당시 GPU 메모리 사용량:

```text
572 MiB / 8188 MiB
```

주의:

- NVIDIA-SMI에 표시되는 CUDA Version은 시스템 드라이버가 지원하는 CUDA 기준이다.
- 실제 Python 런타임에서는 현재 기록상 `torch==2.6.0+cu124` 조합을 사용했다.
- 프로젝트 통합 시 PyTorch/CUDA 조합을 임의로 변경하지 말고 먼저 별도 환경에서 검증한다.

---

## 7. 2차 프로젝트에 적용할 환경 분리 원칙

### A. 학습 환경

```text
Python 3.11
역할:
- STT fine-tuning
- QLoRA/PEFT Adapter 생성
- checkpoint 생성
- epoch 비교
```

학습 결과에서 서비스 쪽으로 넘길 핵심 산출물:

```text
adapter_model.safetensors
adapter_config.json
필요한 tokenizer/processor 설정
선정 checkpoint 정보
```

### B. 프로젝트 실행 환경

```text
Python 3.13.14
역할:
- 최종 STT 추론
- Agent 파이프라인 연결
- API/MCP/FastAPI 등 프로젝트 모듈과 통합
```

실행 환경은 학습 환경의 패키지를 그대로 복제하는 방식이 아니라,
**검증된 Python 3.13 런타임을 유지하면서 Adapter만 불러오는 구조**로 관리한다.

---

## 8. 프로젝트 통합 순서

권장 적용 순서는 다음과 같다.

```text
1. Python 3.13 전용 venv 활성화
        ↓
2. 현재 검증된 STT 핵심 패키지 버전 확인
        ↓
3. Whisper Large-v3-Turbo Base 로드
        ↓
4. Epoch 2 Escape-room Adapter 로드
        ↓
5. CUDA 로드 확인
        ↓
6. 실제 WAV 1개 전사
        ↓
7. 고정 음성 일부 회귀 테스트
        ↓
8. STT → Agent 입력 연결
        ↓
9. MCP / API / FastAPI 등 프로젝트 패키지와 함께 실행
        ↓
10. 충돌 없으면 프로젝트 런타임 버전 고정
```

---

## 9. 버전 충돌 발생 시 확인 순서

2차 프로젝트 통합 중 오류가 생기면 한꺼번에 패키지를 바꾸지 말고 아래 순서로 확인한다.

```text
1. Python 버전 확인
2. 현재 venv가 맞는지 확인
3. torch 버전 확인
4. torch.cuda.is_available() 확인
5. transformers 버전 확인
6. peft 버전 확인
7. adapter_config.json의 Base Model 확인
8. Base Model 단독 로드 확인
9. Adapter 결합 후 로드 확인
10. WAV 단독 추론 확인
11. 마지막으로 전체 Agent 파이프라인 연결 확인
```

이 순서를 쓰면 문제가
**GPU/CUDA 문제인지, Base 모델 문제인지, PEFT Adapter 문제인지, 프로젝트 패키지 충돌인지**
단계를 나눠서 확인할 수 있다.

---

## 10. 현재 확인하지 못한 정보

아래 정보는 현재 제공된 3개 기록만으로는 확정할 수 없다.

- Python 3.11 학습 환경의 전체 `pip freeze`
- Python 3.11의 정확한 torch / transformers / peft 버전
- 최종 Large Epoch 2 Adapter가 Python 3.13에서 실제로 로드됐는지 여부
- Large Epoch 2 실제 WAV 추론이 Python 3.13에서 성공했는지 여부
- 최종 2차 프로젝트 전체 dependency와의 충돌 여부

따라서 **Gate 2를 통과하기 전에는 최종 호환성 검증 완료로 표시하지 않는다.**

---

## 11. Python 3.13 전체 패키지 스냅샷

아래는 기존 `STT_PY313_PACKAGES.txt`의 전체 기록이다.

```text
accelerate==1.15.0
annotated-doc==0.0.5
anyio==4.15.1
certifi==2026.7.22
cffi==2.1.1
charset-normalizer==3.5.1
click==8.5.0
cloudpickle==3.1.2
colorama==0.4.6
decorator==5.3.1
filelock==3.32.3
fsspec==2026.7.0
h11==0.16.0
hf-xet==1.6.0
httpcore==1.0.9
httpx==0.28.1
huggingface_hub==1.32.0
idna==3.20
Jinja2==3.1.6
joblib==1.6.0
lazy-loader==0.6
librosa==1.0.0
llvmlite==0.49.0
markdown-it-py==4.2.0
MarkupSafe==3.0.3
mdurl==0.1.2
mpmath==1.3.0
msgpack==1.2.2
narwhals==2.26.0
networkx==3.6.1
numba==0.67.0
numpy==2.5.2
packaging==26.3
peft==0.21.0
pillow==12.3.0
platformdirs==4.11.12
pooch==1.9.0
psutil==7.2.2
pycparser==3.0
Pygments==2.21.0
PyYAML==6.0.3
regex==2026.9.10
requests==2.34.2
rich==15.0.0
safetensors==0.8.0
scikit-learn==1.9.1
scipy==1.18.1
sentencepiece==0.2.2
setuptools==84.0.0
shellingham==1.5.4
soundfile==0.14.0
soxr==1.1.0
sympy==1.13.1
threadpoolctl==3.7.0
tokenizers==0.23.2
torch==2.6.0+cu124
torchaudio==2.6.0+cu124
torchvision==0.21.0+cu124
tqdm==4.70.1
transformers==5.17.0
typer==0.27.2
typing_extensions==4.16.0
urllib3==2.8.0
wheel==0.48.0
```

---

## 12. 최종 운영 기준

```text
학습:
Python 3.11
    ↓
Escape-room Adapter 생성
    ↓
최종 선정:
Whisper Large-v3-Turbo + Epoch 2 Adapter
    ↓
호환성 검증:
Python 3.13.14 + CUDA 12.4 계열 환경
    ↓
실제 WAV 전사
    ↓
Agent 파이프라인 통합
    ↓
전체 dependency 충돌 검사
    ↓
Gate 2 PASS 후 런타임 버전 고정
```

### 현재 상태

- **Compatibility Gate 1: PASS**
- **Compatibility Gate 2: 아직 최종 Large Epoch 2 대상으로 검증 필요**

이 문서를 2차 프로젝트의 **STT 환경 기준 문서**로 사용한다.
