from backend.schemas import EmotionSignal, IntentResult, IntentType


EQUIPMENT_WORDS = (
    "고장", "안 열려", "이미 열려", "망가", "작동 안", "반응이 없", "장비", "소품",
)
MASTER_WORDS = (
    "직원", "게임마스터", "사람 불러", "직원 불러", "관리자 불러",
)
HINT_WORDS = (
    "힌트", "모르겠", "막혔", "어떻게 풀", "도와줘", "도와주세요",
)
TIME_EXTENSION_WORDS = (
    "시간을 더", "시간 추가",
)
ANSWER_WORDS = (
    "정답", "답 알려", "답만", "정답 알려", "답이 뭐",
)
STRONG_HINT_WORDS = (
    "강한 힌트", "강힌트", "더 직접적인 힌트", "거의 답", "답에 가까운 힌트",
)
TIME_OR_REPEAT_WORDS = (
    "시간 없어", "시간이 없어", "시간 얼마 안", "계속 했", "계속 해도", "여러 번", "몇 번이나", "반복",
)
HELPLESS_WORDS = (
    "포기", "못 풀겠", "진짜 모르겠", "너무 답답", "아무것도 모르겠", "도저히 모르겠",
)


def classify_intent_baseline(message: str) -> IntentResult:
    """API 키 없이도 데모 흐름을 확인하기 위한 보수적 baseline.

    실제 LLM과 비교하기 위한 키워드 기준선이다. 프로덕션 장애를 숨기는
    자동 fallback으로 사용하지 않는다.
    """
    text = message.strip().lower()

    if not text:
        return IntentResult(
            intent=IntentType.UNCLEAR,
            needs_clarification=True,
            reason="EMPTY_MESSAGE",
        )

    if any(word in text for word in MASTER_WORDS):
        return IntentResult(
            intent=IntentType.MASTER_REQUEST,
            reason="DIRECT_MASTER_REQUEST",
        )

    if any(word in text for word in EQUIPMENT_WORDS):
        return IntentResult(
            intent=IntentType.EQUIPMENT_ISSUE,
            reason="EQUIPMENT_KEYWORD",
        )

    # 운영 확장 기획안: 시간 연장 요청은 자동으로 타이머를 바꾸지 않고
    # 게임마스터 승인 대상으로 분류한다.
    if any(word in text for word in TIME_EXTENSION_WORDS):
        return IntentResult(
            intent=IntentType.TIME_EXTENSION_REQUEST,
            reason="TIME_EXTENSION_REQUEST",
        )

    direct_answer_request = any(word in text for word in ANSWER_WORDS)
    strong_hint_request = any(word in text for word in STRONG_HINT_WORDS)

    # 최신 기획안의 보수적 강한 좌절 기준:
    # 시간/반복 시도 언급 + 무력감/포기 표현이 함께 있을 때만 True.
    frustration_high = (
        any(word in text for word in TIME_OR_REPEAT_WORDS)
        and any(word in text for word in HELPLESS_WORDS)
    )

    emotion = EmotionSignal.HIGH if frustration_high else EmotionSignal.LOW

    if (
        direct_answer_request
        or strong_hint_request
        or frustration_high
        or any(word in text for word in HINT_WORDS)
    ):
        return IntentResult(
            intent=IntentType.HINT,
            emotion=emotion,
            reason="HINT_REQUEST",
            direct_answer_request=direct_answer_request,
            strong_hint_request=strong_hint_request,
            frustration_high=frustration_high,
        )

    return IntentResult(
        intent=IntentType.UNCLEAR,
        emotion=emotion,
        needs_clarification=True,
        reason="INTENT_UNCLEAR",
        frustration_high=frustration_high,
    )
