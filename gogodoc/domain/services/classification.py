"""정상범위 및 응급 이상치 기준 플래그 판정 (순수 도메인 규칙)

성별·나이 파라미터 기반 판정 - 성인 기준 미해당(소아 등) 시 판정 불가
"""

from gogodoc.domain.models import Flag
from gogodoc.domain.reference import reference_dict, panic_values, clinical_bands, findings

# 정상범위 이탈폭 주의/이상 구분 기준 (범위 폭 대비 비율) - 임상 밴드 미정의 항목 폴백
_CAUTION_RATIO = 0.5


def classify_finding(item: str, text: str) -> Flag | None:
    """정성 소견 텍스트 플래그 판정 - 소견 KB 매칭 시 Flag, 미수록·미매칭 시 None(폴백)"""
    card = findings.lookup_finding(item, text)
    return Flag(card["flag"]) if card else None


def classify(canonical: str, value: float | None, sex: str, age: int) -> Flag:
    """플래그 판정 - 성인 범위 게이트 → 임상 밴드 우선, 미정의 시 정상범위·편차 폴백"""
    # 수치 인식 불가 - 확인필요
    if value is None:
        return Flag.CHECK_NEEDED

    entry = reference_dict.lookup(canonical)

    # 패닉 전용 항목(REFERENCE 미존재) - 패닉 검사 후 알수없음
    if not entry:
        if panic_values.check_panic(canonical, value):
            return Flag.EMERGENCY
        return Flag.UNKNOWN

    # 성인 범위 외(소아 등) - 판정 불가 (밴드도 성인 기준)
    rng = reference_dict.select_range(entry, sex, age)
    if not rng:
        return Flag.UNKNOWN

    # 항목별 임상 밴드 우선 (정상/주의/이상/응급 컷오프)
    band = clinical_bands.classify_band(canonical, value, sex)
    if band is not None:
        return Flag(band)

    # 밴드 미정의 - 패닉 밸류 + 정상범위 편차 폴백
    if panic_values.check_panic(canonical, value):
        return Flag.EMERGENCY

    low, high = rng
    if low <= value <= high:
        return Flag.NORMAL

    span = high - low or 1.0
    deviation = (value - high) / span if value > high else (low - value) / span
    return Flag.CAUTION if deviation <= _CAUTION_RATIO else Flag.ABNORMAL
