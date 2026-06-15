"""응급 이상치(패닉 밸류) 기준 - 감지 시 즉시 내원 안내 우선 표시

D1 스키마 정의 대상
조건: low(이하) 또는 high(이상) 임계값 - None 이면 해당 방향 미적용
"""

# 표준 항목명 -> {low, high, message}
# TODO: D1 에서 항목별 패닉 밸류 기준 검증 및 확장
PANIC_VALUES: dict[str, dict] = {
    "공복혈당": {
        "low": 50,
        "high": 500,
        "message": "혈당 응급 이상치 - 즉시 의료기관 내원 필요",
    },
    "나트륨": {
        "low": 120,
        "high": 160,
        "message": "나트륨 응급 이상치 - 즉시 의료기관 내원 필요",
    },
    "칼륨": {
        "low": 2.5,
        "high": 6.5,
        "message": "칼륨 응급 이상치 - 즉시 의료기관 내원 필요",
    },
}


def check_panic(canonical_name: str, value: float | None) -> str | None:
    """패닉 밸류 해당 시 안내 메시지 반환"""
    if value is None:
        return None
    rule = PANIC_VALUES.get(canonical_name)
    if not rule:
        return None
    low, high = rule.get("low"), rule.get("high")
    if (low is not None and value <= low) or (high is not None and value >= high):
        return rule["message"]
    return None
