"""복합검사 값 분해 - 한 셀의 다중 수치를 개별 (항목명, 수치)로 분리 (순수 도메인 규칙)

종합검진 표가 "공복혈당380/혈압200"처럼 한 칸에 복수 결과를 담는 경우를 분해한다.
분해 결과는 각각 정규화·분류를 거쳐 케이스 위험도는 최댓값으로 집계한다(상위 호출).
'혈압'·'총콜' 등 축약 표기는 표준 항목명으로 보정한다.
"""

import re

# 축약 표기 -> 표준 항목명 (정규화 전 보정)
_NAME_ALIASES = {
    "혈압": "수축기혈압",
    "총콜": "총콜레스테롤",
}

# 항목명(한글·영문·하이픈) + 수치 토큰
_TOKEN = re.compile(r"(?P<name>[A-Za-z가-힣]+(?:-[A-Za-z0-9]+)?)\s*(?P<value>\d+(?:\.\d+)?)")


def parse_composite(value: str) -> list[tuple[str, float]]:
    """복합검사 문자열을 [(항목명, 수치)] 로 분해 - 매칭 없으면 빈 리스트"""
    items = []
    for m in _TOKEN.finditer(value or ""):
        name = _NAME_ALIASES.get(m.group("name"), m.group("name"))
        items.append((name, float(m.group("value"))))
    return items


def is_composite(value: str) -> bool:
    """복합검사 값(다중 수치) 여부 - 수치 토큰 2개 이상"""
    return len(_TOKEN.findall(value or "")) >= 2
