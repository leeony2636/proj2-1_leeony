import os

# 테스트는 외부 API 비용 없이 명시적 baseline을 사용한다.
os.environ.setdefault("LLM_PROVIDER", "baseline")
