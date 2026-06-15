"""항목 해설 dict - 표준 항목명별 정상범위·해설·주의사항

근거 기반 해석의 핵심 - LLM은 이 dict 범위 내에서만 설명 생성
출처: 건강보험심사평가원, 질병관리청 국가건강정보포털, 대한임상검사정도관리협회
정상범위는 성별 의존 항목 분리 (sex 키: "common" | "male" | "female")
"""

# 표준 항목명 -> 해설 정보
# TODO: D1 PubMed MCP + ICD-10 Codes MCP 로 항목별 근거 보강 후 확장
REFERENCE: dict[str, dict] = {
    "ALT": {
        "ranges": {"common": (0, 40)},
        "unit": "U/L",
        "explanation": "간세포 손상 시 올라가는 효소 수치",
        "caution": "높으면 간 기능 추적 관찰 권장",
        "source": "대한임상검사정도관리협회",
    },
    "AST": {
        "ranges": {"common": (0, 40)},
        "unit": "U/L",
        "explanation": "간·근육 손상 시 올라가는 효소 수치",
        "caution": "ALT 와 함께 해석 권장",
        "source": "대한임상검사정도관리협회",
    },
    "공복혈당": {
        "ranges": {"common": (70, 99)},
        "unit": "mg/dL",
        "explanation": "공복 상태 혈중 포도당 농도",
        "caution": "100-125 공복혈당장애, 126 이상 당뇨 의심",
        "source": "질병관리청 국가건강정보포털",
    },
    "당화혈색소": {
        "ranges": {"common": (4.0, 5.6)},
        "unit": "%",
        "explanation": "최근 2-3개월 평균 혈당 지표",
        "caution": "5.7-6.4 당뇨 전단계, 6.5 이상 당뇨 의심",
        "source": "질병관리청 국가건강정보포털",
    },
    "총콜레스테롤": {
        "ranges": {"common": (0, 200)},
        "unit": "mg/dL",
        "explanation": "혈중 전체 콜레스테롤 양",
        "caution": "240 이상 높음, 식이·운동 관리 권장",
        "source": "건강보험심사평가원",
    },
}


def lookup(canonical_name: str) -> dict | None:
    """표준 항목명으로 해설 정보 조회"""
    return REFERENCE.get(canonical_name)


def range_for(entry: dict, sex: str) -> tuple[float, float] | None:
    """성별 고려 정상범위 반환 - 성별 분리 항목 우선, 없으면 common"""
    ranges = entry.get("ranges", {})
    return ranges.get(sex) or ranges.get("common")
