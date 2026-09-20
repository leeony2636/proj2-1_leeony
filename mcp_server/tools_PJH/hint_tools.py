# -*- coding: utf-8 -*-

# ==========================================================
# MCP 도구 코드 모음 (힌트 제공 관련 도구)
# 이 파일은 데이터를 직접 갖고 있지 않고, 테마별 파일에서 데이터를 가져와 쓴다.
# (같은 폴더 안에 theme_professor_lab.py, theme_last_train.py, common_tools.py가 있어야 동작한다)
# ==========================================================

from .data.theme_professor_lab import THEME_PROFESSOR_LAB
from .data.theme_last_train import THEME_LAST_TRAIN
from .common_tools import 문제_찾기, 문제_개수_확인, 재활용_문제_목록


def get_approved_hint(테마, 문제번호, 강도):
    """
    테마 데이터에서 해당 문제를 찾아, 요청한 강도(weak/strong)의 힌트 내용을 돌려준다.

    입력:
        테마     - THEME_PROFESSOR_LAB 같은 테마 딕셔너리
        문제번호  - "P01" 같은 문제 고유번호
        강도     - "weak"(약한 힌트) 또는 "strong"(강한 힌트)

    출력:
        {
            "status": "OK" 또는 "NOT_FOUND" 또는 "INVALID_STRENGTH",
            "puzzle_id": "P01",
            "hint_strength": "weak",
            "hint_text": "책상 위에 뭔가 표시된 물건이 있는지 살펴보세요"
        }
    """
    문제 = 문제_찾기(테마, 문제번호)

    if 문제 is None:
        return {
            "status": "NOT_FOUND",
            "puzzle_id": 문제번호,
            "hint_strength": 강도,
            "hint_text": None,
        }

    if 강도 == "weak":
        힌트_내용 = 문제["hint_weak"]
    elif 강도 == "strong":
        힌트_내용 = 문제["hint_strong"]
    else:
        return {
            "status": "INVALID_STRENGTH",
            "puzzle_id": 문제번호,
            "hint_strength": 강도,
            "hint_text": None,
        }

    return {
        "status": "OK",
        "puzzle_id": 문제번호,
        "hint_strength": 강도,
        "hint_text": 힌트_내용,
    }


# ==========================================================
# MCP 도구 2: 힌트_강도_판단 (SKILL.md 판단 기준을 코드로 옮긴 함수)
#
# 주의: 이 함수는 "남은시간"과 "남은 문제 비율"을 이미 계산된 숫자로 받는다.
#       (get_game_session이 계산해서 넘겨준다고 가정)
#       손님 발화를 보고 몇 번 문제인지 알아내는 것(진도 추정)은
#       이 함수의 일이 아니라, 별도의 다른 함수가 할 일이다.
#
# 용어 주의: "남은 문제 비율(remaining_puzzle_ratio)"은 아직 안 푼 문제의 비율이다.
#           "해결한 비율"이 아니라 반대 개념이므로 부등호 방향에 주의한다.
# ==========================================================

def 힌트_강도_판단(남은시간_분, 남은_문제_비율, 정답요구여부, 재요청여부, 감정강함여부):
    """
    SKILL.md의 "판단 기준" 1번 우선순위를 그대로 코드로 옮긴 함수.
    우선순위: 정답요구 → 재요청 오버라이드 → 감정 오버라이드 → 기본규칙

    입력:
        남은시간_분     - 숫자 (예: 12)
        남은_문제_비율   - 0.0 ~ 1.0 사이 숫자. 아직 안 푼 문제의 비율 (예: 0.58 = 58%가 남음)
        정답요구여부     - True/False
        재요청여부       - True/False (약한 힌트 받고 1분 이내 같은 문제로 재요청했는지)
        감정강함여부     - True/False (시간·시도 경과 + 무력감이 함께 감지됐는지)

    출력:
        {
            "hint_strength": "strong",
            "reason_code": "ANSWER_REQUEST"
        }
    """

    # 1순위: 정답을 직접 요구했는가?
    if 정답요구여부 == True:
        return {
            "hint_strength": "strong",
            "reason_code": "ANSWER_REQUEST",
        }

    # 2순위: 재요청인가?
    if 재요청여부 == True:
        return {
            "hint_strength": "strong",
            "reason_code": "RE_REQUEST_OVERRIDE",
        }

    # 3순위: 감정이 강한가?
    if 감정강함여부 == True:
        return {
            "hint_strength": "strong",
            "reason_code": "EMOTION_OVERRIDE",
        }

    # 4순위: 위 세 가지가 다 해당 안 되면 기본규칙 적용
    # 남은 문제 비율이 50% "이상"이면(=아직 절반 넘게 남았으면) 강한 힌트 후보
    if 남은시간_분 <= 15 and 남은_문제_비율 >= 0.5:
        return {
            "hint_strength": "strong",
            "reason_code": "BASE_RULE_TIME_AND_PROGRESS",
        }
    else:
        return {
            "hint_strength": "weak",
            "reason_code": "BASE_RULE_DEFAULT",
        }


# ==========================================================
# 3단계: 판단 함수 + 조회 함수를 합친 최종 함수
# 이게 실제로 Agent가 호출하게 될, 완성된 "힌트 제공" 흐름이다.
# ==========================================================

def 힌트_제공(테마, 문제번호, 남은시간_분, 남은_문제_비율, 정답요구여부, 재요청여부, 감정강함여부):
    """
    손님의 현재 상황을 받아서, 최종적으로 어떤 힌트를 줄지까지 결정하는 함수.

    흐름:
        1) 힌트_강도_판단 함수로 weak/strong 중 무엇을 줄지 정한다.
        2) get_approved_hint 함수로 그 강도에 맞는 실제 힌트 텍스트를 꺼내온다.
        3) 판단 이유(reason_code)까지 합쳐서 하나의 결과로 돌려준다.

    중요: 이 함수의 반환값 중 "손님_응답"이 실제로 화면에 나가는 부분이다.
         puzzle_id(문제 번호)는 여기에 절대 포함하지 않는다 — 손님이 번호를 알면
         순서대로 찾아 풀 수 있게 되어 게임의 재미가 사라지기 때문이다.
         (SKILL.md "하지 말아야 할 것" 참고)
         puzzle_id는 "내부_로그"쪽에만 남겨서, 개발자가 디버깅할 때만 확인한다.
    """

    판단결과 = 힌트_강도_판단(
        남은시간_분=남은시간_분,
        남은_문제_비율=남은_문제_비율,
        정답요구여부=정답요구여부,
        재요청여부=재요청여부,
        감정강함여부=감정강함여부,
    )

    조회결과 = get_approved_hint(테마, 문제번호, 판단결과["hint_strength"])

    # 손님 화면에 실제로 나가는 응답 — puzzle_id를 포함하지 않는다.
    손님_응답 = {
        "status": 조회결과["status"],
        "hint_strength": 판단결과["hint_strength"],
        "hint_text": 조회결과["hint_text"],
    }

    # 개발자가 디버깅할 때만 보는 내부 기록 — 여기에는 puzzle_id와 판단 이유를 남긴다.
    내부_로그 = {
        "puzzle_id": 문제번호,
        "reason_code": 판단결과["reason_code"],
    }

    return {
        "손님_응답": 손님_응답,
        "내부_로그": 내부_로그,
    }


# ==========================================================
# 테스트 코드 (이 파일을 직접 실행했을 때만 동작함)
# ==========================================================

if __name__ == "__main__":

    print("===== 데이터 확인 =====")
    개수1 = 문제_개수_확인(THEME_PROFESSOR_LAB)
    print("교수님의 연구실 문제 개수:", 개수1, "/", THEME_PROFESSOR_LAB["total_puzzles"])
    개수2 = 문제_개수_확인(THEME_LAST_TRAIN)
    print("마지막 열차 문제 개수:", 개수2, "/", THEME_LAST_TRAIN["total_puzzles"])

    print()
    print("===== get_approved_hint 테스트 =====")
    결과 = get_approved_hint(THEME_PROFESSOR_LAB, "P01", "weak")
    print("P01 약한 힌트:", 결과)
    결과 = get_approved_hint(THEME_PROFESSOR_LAB, "P01", "strong")
    print("P01 강한 힌트:", 결과)
    결과 = get_approved_hint(THEME_PROFESSOR_LAB, "P99", "weak")
    print("없는 문제(P99):", 결과)

    print()
    print("===== 힌트_강도_판단 테스트 =====")
    # 시간 여유(40분) + 남은 문제 적음(0.2 = 20%만 남음) → 정답요구가 있으니 무조건 강함
    결과 = 힌트_강도_판단(남은시간_분=40, 남은_문제_비율=0.2, 정답요구여부=True, 재요청여부=False, 감정강함여부=False)
    print("정답 요구:", 결과)
    # 시간 부족(10분) + 남은 문제 많음(0.7 = 70% 남음) → 기본규칙으로 강함
    결과 = 힌트_강도_판단(남은시간_분=10, 남은_문제_비율=0.7, 정답요구여부=False, 재요청여부=False, 감정강함여부=False)
    print("기본규칙(강함 조건):", 결과)

    print()
    print("===== 힌트_제공 (최종 통합) 테스트 =====")
    # 시간 여유(45분) + 남은 문제 많음(0.9 = 90% 남음, 기본규칙만 보면 애매) + 감정강함 → 오버라이드로 강함
    결과 = 힌트_제공(
        테마=THEME_PROFESSOR_LAB,
        문제번호="P01",
        남은시간_분=45,
        남은_문제_비율=0.9,
        정답요구여부=False,
        재요청여부=False,
        감정강함여부=True,
    )
    print("시나리오 A (감정 오버라이드):")
    print("  손님_응답:", 결과["손님_응답"])
    print("  내부_로그(개발자용, puzzle_id 포함):", 결과["내부_로그"])

    # 시간 여유(50분) + 남은 문제 적음(0.1 = 10%만 남음) + 정답요구 → 오버라이드로 강함
    결과 = 힌트_제공(
        테마=THEME_PROFESSOR_LAB,
        문제번호="P05",
        남은시간_분=50,
        남은_문제_비율=0.1,
        정답요구여부=True,
        재요청여부=False,
        감정강함여부=False,
    )
    print("시나리오 B (정답 직접 요구):")
    print("  손님_응답:", 결과["손님_응답"])
    print("  내부_로그(개발자용, puzzle_id 포함):", 결과["내부_로그"])
