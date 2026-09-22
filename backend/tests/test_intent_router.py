from backend.schemas import IntentType
from backend.services.baseline_router import classify_intent_baseline


def test_equipment_routes_to_master_intent():
    assert classify_intent_baseline("자물쇠가 고장난 것 같아요").intent == IntentType.EQUIPMENT_ISSUE


def test_direct_master_request():
    assert classify_intent_baseline("직원 불러주세요").intent == IntentType.MASTER_REQUEST


def test_hint_request():
    assert classify_intent_baseline("힌트 주세요").intent == IntentType.HINT


def test_direct_answer_request_is_structured_not_revealed():
    result = classify_intent_baseline("정답 알려줘")
    assert result.intent == IntentType.HINT
    assert result.direct_answer_request is True


def test_frustration_requires_time_or_repeat_plus_helplessness():
    mild = classify_intent_baseline("진짜 모르겠어요 힌트 주세요")
    strong = classify_intent_baseline("시간이 없어. 계속 해도 못 풀겠어요")
    assert mild.frustration_high is False
    assert strong.frustration_high is True


def test_time_extension_routes_to_game_master_approval():
    result = classify_intent_baseline("시간을 더 주면 안 되나요?")
    assert result.intent == IntentType.TIME_EXTENSION_REQUEST
    assert result.reason == "TIME_EXTENSION_REQUEST"
