"""정상범위 및 응급 이상치 기준 플래그 판정 (순수 도메인 규칙)"""

from gogodoc.domain.models import Flag
from gogodoc.domain.reference import reference_dict, panic_values

# 정상범위 이탈폭 주의/이상 구분 기준 (범위 폭 대비 비율)
_CAUTION_RATIO = 0.5


def classify(canonical: str, value: float | None, sex: str) -> Flag:
    """정상범위 및 패닉 밸류 기준 플래그 판정"""
    if value is None:
        return Flag.UNKNOWN

    # 패닉 밸류 우선 검사
    if panic_values.check_panic(canonical, value):
        return Flag.EMERGENCY

    entry = reference_dict.lookup(canonical)
    if not entry:
        return Flag.UNKNOWN

    rng = reference_dict.range_for(entry, sex)
    if not rng:
        return Flag.UNKNOWN

    low, high = rng
    if low <= value <= high:
        return Flag.NORMAL

    # 정상범위 이탈폭 기준 주의/이상 구분
    span = high - low or 1.0
    deviation = (value - high) / span if value > high else (low - value) / span
    return Flag.CAUTION if deviation <= _CAUTION_RATIO else Flag.ABNORMAL
