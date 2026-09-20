from backend.schemas import EmotionSignal, IntentResult, IntentType


EQUIPMENT_WORDS = (
    "고장", "안 열려", "이미 열려", "망가", "작동 안", "장비", "소품",
)
MASTER_WORDS = (
    "직원", "게임마스터", "사람 불러", "직원 불러", "관리자 불러",
)
HINT_WORDS = (
    "힌트", "모르겠", "막혔", "어떻게 풀", "도와줘", "도와주세요",
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

    핵심은 자연어를 구조화하는 것까지이며, 최종 WEAK/STRONG 판정은
    backend/services/hint_decision.py의 코드 규칙이 담당한다.
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
