import os

# 테스트는 외부 API 비용 없이 명시적 baseline을 사용한다.
os.environ.setdefault("LLM_PROVIDER", "baseline")

# 게임마스터 API는 실제 환경에서 fail-closed가 기본이다. 테스트 스위트의
# 기존 성공 경로는 명시적인 test 환경 + local bypass에서만 통과시킨다.
# 개별 인증 경계 테스트는 monkeypatch로 이 값을 제거/변경해 401/403을 검증한다.
os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("GM_AUTH_BYPASS_LOCAL", "true")
