# -*- coding: utf-8 -*-

# ==========================================================
# 테마 데이터: 교수님의 연구실
# 손님이 이 문제를 풀 때마다 이 데이터를 조회해서 힌트를 내려준다.
# 프로그램을 끄면 사라지는 파이썬 변수라, 세션이 끝나면 자동으로 초기화된다.
# ==========================================================

# 테마 1: 교수님의 연구실 (난이도 2/5, 총 12문제)
THEME_PROFESSOR_LAB = {
    "theme_id": "THEME_01",          # 테마를 구분하는 고유 번호
    "theme_name": "교수님의 연구실",   # 화면에 보여줄 테마 이름
    "difficulty": 2,                  # 난이도 (5점 만점)
    "total_puzzles": 12,              # 이 테마의 전체 문제 수 (진도율 계산에 씀)

    "puzzles": [
        {
            "puzzle_id": "P01",
            "order": 1,
            "description": "책상 위 탁상달력에 3월 14일만 빨간 동그라미",
            "location": "책상 위",
            "answer": "314",
            "hint_weak": "책상 위에 뭔가 표시된 물건이 있는지 살펴보세요",
            "hint_strong": "달력에 3월 14일이 동그라미 쳐져 있어요. 숫자만 뽑으면 314, 책상 서랍 자물쇠에 넣으세요",
            "note": None,   # 단서 재활용/다중조합이 없는 일반 문제는 None(없음)으로 표시
        },
        {
            "puzzle_id": "P02",
            "order": 2,
            "description": "서랍 속 학생 명렬표, 이름 옆 출석 체크 개수 세기",
            "location": "책상 서랍(1번으로 열림)",
            "answer": "07",
            "hint_weak": "서랍에서 나온 종이에 체크 표시가 몇 개인지 세어보세요",
            "hint_strong": "명렬표의 체크 표시는 총 7개예요. 07을 책장 파일함에 입력하세요",
            "note": None,
        },
        {
            "puzzle_id": "P03",
            "order": 3,
            "description": "파일함 속 사진 4장, 뒷면에 각각 알파벳 (L·O·C·K)",
            "location": "책장 파일함",
            "answer": "LOCK",
            "hint_weak": "사진들을 뒤집어 보세요",
            "hint_strong": "사진 뒷면 알파벳을 순서대로 모으면 L-O-C-K, 캐비닛 글자 자물쇠에 넣으세요",
            "note": None,
        },
        {
            "puzzle_id": "P04",
            "order": 4,
            "description": "캐비닛 안 시계 모형, 바늘이 8시 20분 고정",
            "location": "캐비닛",
            "answer": "0820",
            "hint_weak": "캐비닛 안 시계가 몇 시를 가리키는지 보세요",
            "hint_strong": "시계는 8시 20분이에요. 0820을 금고에 넣으세요",
            "note": None,
        },
        {
            "puzzle_id": "P05",
            "order": 5,
            "description": "금고 속 지도, 빨간 핀 4개가 동서남북에 하나씩",
            "location": "금고",
            "answer": "위-오른쪽-아래-왼쪽",
            "hint_weak": "지도에 꽂힌 핀들이 어느 방향을 가리키는지 순서대로 보세요",
            "hint_strong": "핀은 북→동→남→서 순서로 번호가 붙어 있어요. 방향자물쇠를 위-오른쪽-아래-왼쪽 순으로 돌리면 벽 액자가 열립니다",
            "note": None,
        },
        {
            "puzzle_id": "P06",
            "order": 6,
            "description": "액자 뒤 메모 '내 수업은 늘 3층 2호실'",
            "location": "벽 액자",
            "answer": "302",
            "hint_weak": "액자 뒤 메모에 적힌 장소를 숫자로 바꿔보세요",
            "hint_strong": "3층 2호실이니 302예요. 수납장에 입력하세요",
            "note": None,
        },
        {
            "puzzle_id": "P07",
            "order": 7,
            "description": "수납장 속 색연필 5자루, 길이가 제각각",
            "location": "수납장",
            "answer": "빨-노-파",
            "hint_weak": "색연필들을 길이 순으로 세워보세요",
            "hint_strong": "긴 것부터 빨강-노랑-파랑이에요. 이 순서로 색상 자물쇠를 맞추세요",
            "note": None,
        },
        {
            "puzzle_id": "P08",
            "order": 8,
            "description": "캐비닛 2단 속 영수증 3장, 금액 합산",
            "location": "캐비닛 2단",
            "answer": "1250",
            "hint_weak": "영수증 금액을 모두 더해보세요",
            "hint_strong": "3장 합이 12,500원이에요. 앞 4자리 1250을 책상 밑 상자에 넣으세요",
            "note": None,
        },
        {
            "puzzle_id": "P09",
            "order": 9,
            "description": "상자 속 퍼즐 조각 6개, 맞추면 별 모양",
            "location": "책상 밑 상자",
            "answer": "별 모양 완성",
            "hint_weak": "조각들을 바닥에 놓고 맞춰보세요",
            "hint_strong": "조각 6개를 맞추면 별 모양이 됩니다. 완성하면 옆 선반의 램프가 켜져요",
            "note": None,
        },
        {
            "puzzle_id": "P10",
            "order": 10,
            "description": "램프 불빛에 비친 벽면의 숨은 글씨 '1987'",
            "location": "램프 켜진 후 벽",
            "answer": "1987",
            "hint_weak": "램프가 켜진 벽면을 자세히 보세요",
            "hint_strong": "불빛에 1987이라는 숫자가 드러나요. 마지막 캐비닛에 입력하세요",
            "note": None,
        },
        {
            "puzzle_id": "P11",
            "order": 11,
            "description": "캐비닛 속 USB와 노트, 노트 첫 글자만 이어 읽기",
            "location": "마지막 캐비닛",
            "answer": "EXIT",
            "hint_weak": "노트 각 줄의 첫 글자만 세로로 읽어보세요",
            "hint_strong": "첫 글자를 세로로 읽으면 EXIT예요. 문 옆 패널에 입력하세요",
            "note": None,
        },
        {
            "puzzle_id": "P12",
            "order": 12,
            "description": "패널 열리면 최종 레버",
            "location": "출입문 패널",
            "answer": "레버 당기기",
            "hint_weak": "패널 안에 손잡이가 보일 거예요",
            "hint_strong": "레버를 아래로 당기면 문이 열립니다",
            "note": None,
        },
    ],
}


# ==========================================================
# 이 파일만 단독으로 실행했을 때, 데이터가 잘 만들어졌는지 확인하는 코드
# ==========================================================

if __name__ == "__main__":
    실제_개수 = 0
    for 문제 in THEME_PROFESSOR_LAB["puzzles"]:
        실제_개수 = 실제_개수 + 1

    print("테마 이름:", THEME_PROFESSOR_LAB["theme_name"])
    print("입력된 문제 개수:", 실제_개수, "/ total_puzzles 표기:", THEME_PROFESSOR_LAB["total_puzzles"])
