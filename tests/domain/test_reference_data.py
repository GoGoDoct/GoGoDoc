"""D1·D2 해설 dict·패닉 밸류 데이터 검증 - 성별·나이 룰 및 데이터 정합성"""

from gogodoc.domain.models import Flag
from gogodoc.domain.services import classification
from gogodoc.domain.reference import reference_dict, panic_values

# 해설 dict 필수 키
_REQUIRED_KEYS = {"ranges", "unit", "explanation", "caution", "source"}
# 정상범위 룰 필수 키
_RULE_KEYS = {"sex", "age_min", "age_max", "low", "high"}


def test_core_item_coverage():
    # 핵심 항목 10개 이상 확보
    assert len(reference_dict.REFERENCE) >= 10


def test_entry_schema_consistency():
    # 모든 항목·룰이 필수 키 보유 및 범위 유효
    for name, entry in reference_dict.REFERENCE.items():
        assert _REQUIRED_KEYS <= set(entry), f"{name} 필수 키 누락"
        assert entry["ranges"], f"{name} 룰 없음"
        for rule in entry["ranges"]:
            assert _RULE_KEYS <= set(rule), f"{name} 룰 키 누락"
            assert rule["low"] <= rule["high"], f"{name} 범위 오류"
            assert rule["age_min"] <= rule["age_max"], f"{name} 나이 밴드 오류"


def test_sex_specific_gtp():
    # 감마지티피 - 동일 값이 성별에 따라 다른 판정
    assert classification.classify("감마지티피", 50, "male", 40) == Flag.NORMAL
    assert classification.classify("감마지티피", 50, "female", 40) != Flag.NORMAL


def test_sex_specific_creatinine():
    # 크레아티닌 - 남성 정상, 여성 범위 초과
    assert classification.classify("크레아티닌", 1.3, "male", 40) == Flag.NORMAL
    assert classification.classify("크레아티닌", 1.3, "female", 40) != Flag.NORMAL


def test_age_based_resolution():
    # 동일 값·성별이라도 성인/소아 나이에 따라 판정 달라짐
    assert classification.classify("ALT", 20, "male", 40) == Flag.NORMAL
    assert classification.classify("ALT", 20, "male", 12) == Flag.UNKNOWN


def test_select_range_pediatric_none():
    # 성인 밴드 미해당 시 범위 None
    entry = reference_dict.lookup("ALT")
    assert reference_dict.select_range(entry, "male", 40) is not None
    assert reference_dict.select_range(entry, "male", 10) is None


def test_hdl_low_is_flagged():
    # HDL 은 낮을수록 위험 - 하한 미만 플래그
    assert classification.classify("HDL 콜레스테롤", 30, "male", 40) != Flag.NORMAL


def test_panic_potassium():
    # 칼륨 응급 수치 - 패닉 감지 및 응급 플래그
    assert panic_values.check_panic("칼륨", 6.8) is not None
    assert classification.classify("칼륨", 6.8, "male", 40) == Flag.EMERGENCY


def test_panic_sodium_both_directions():
    # 나트륨 저·고 양방향 패닉 감지
    assert panic_values.check_panic("나트륨", 118) is not None
    assert panic_values.check_panic("나트륨", 165) is not None
    assert panic_values.check_panic("나트륨", 140) is None
