# -*- coding: utf-8 -*-

# ==========================================================
# MCP 도구: get_puzzle_context
#
# 역할: 지금 손님이 어떤 문제를 말하고 있는지 LLM이 판단할 수 있도록,
#       문제의 "맥락 정보"(설명, 위치, 재활용 여부)를 조회해서 넘겨준다.
#
# 주의: 이 도구는 정답이나 힌트 내용은 절대 돌려주지 않는다.
#       (그건 get_approved_hint의 역할이지, 이 도구의 역할이 아니다)
#       그리고 여기서 조회한 puzzle_id도 손님에게 그대로 노출하면 안 된다.
#       (SKILL.md "하지 말아야 할 것" 참고)
# ==========================================================

from .data.theme_professor_lab import THEME_PROFESSOR_LAB
from .data.theme_last_train import THEME_LAST_TRAIN
from .common_tools import 문제_찾기


def get_puzzle_context(테마, 문제번호):
    """
    문제 하나의 "맥락 정보"만 조회한다. 정답·힌트는 포함하지 않는다.

    입력:
        테마      - THEME_PROFESSOR_LAB 같은 테마 딕셔너리
        문제번호   - "P05" 같은 내부 문제번호 (LLM이 이전 대화 맥락에서 추정한 값)

    출력:
        {
            "status": "OK",
            "description": "금고 속 지도, 빨간 핀 4개가 동서남북에 하나씩",
            "location": "금고",
            "has_reuse_note": True,   # 이 문제가 재활용/다중조합과 관련 있는지 여부
        }

        (주의: answer, hint_weak, hint_strong, puzzle_id는 여기 포함되지 않는다)
    """
    문제 = 문제_찾기(테마, 문제번호)

    if 문제 is None:
        return {
            "status": "NOT_FOUND",
            "description": None,
            "location": None,
            "has_reuse_note": None,
        }

    # note 필드가 채워져 있는지(=재활용/다중조합 문제인지) True/False로 변환한다.
    재활용_여부 = (문제["note"] is not None)

    return {
        "status": "OK",
        "description": 문제["description"],
        "location": 문제["location"],
        "has_reuse_note": 재활용_여부,
    }


def 전체_문제_맥락_목록(테마):
    """
    LLM이 "지금 손님 발화가 몇 번 문제 얘기인지" 판단할 때,
    테마의 모든 문제 설명을 한 번에 훑어볼 수 있도록 리스트로 돌려주는 함수.

    이 리스트도 puzzle_id 대신, LLM이 내부적으로만 쓰는 참조용 순번을 쓴다.
    (실제로 puzzle_id를 완전히 숨기려면 백엔드에서 별도 매핑을 두어야 하지만,
     지금 단계에서는 "이 정보가 LLM 프롬프트 재료용이지 손님 응답이 아니다"
     라는 점을 명확히 하는 것이 핵심이다)
    """
    결과 = []
    for 문제 in 테마["puzzles"]:
        결과.append({
            "description": 문제["description"],
            "location": 문제["location"],
        })
    return 결과


# ==========================================================
# 테스트 코드
# ==========================================================

if __name__ == "__main__":
    print("===== get_puzzle_context 테스트 =====")

    # 정상 케이스: P05 문제(재활용 없음, 교수님의 연구실은 재활용 문제가 없음)
    결과 = get_puzzle_context(THEME_PROFESSOR_LAB, "P05")
    print("교수님의 연구실 P05:", 결과)

    # 재활용 문제가 있는 마지막 열차 테마 확인
    결과 = get_puzzle_context(THEME_LAST_TRAIN, "P04")
    print("마지막 열차 P04(재활용 문제):", 결과)

    # 없는 문제 조회
    결과 = get_puzzle_context(THEME_PROFESSOR_LAB, "P99")
    print("없는 문제:", 결과)

    print()
    print("===== 전체_문제_맥락_목록 테스트 (일부만 출력) =====")
    전체_목록 = 전체_문제_맥락_목록(THEME_PROFESSOR_LAB)
    print("교수님의 연구실 총 문제 맥락 개수:", len(전체_목록))
    print("첫 번째 항목:", 전체_목록[0])
