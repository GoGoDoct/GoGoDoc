"""D1 해설 dict·패닉 밸류 데이터 검증 - 성별 분리 및 데이터 정합성"""

from gogodoc.domain.models import Flag
from gogodoc.domain.services import classification
from gogodoc.domain.reference import reference_dict, panic_values

# 해설 dict 필수 키
_REQUIRED_KEYS = {"ranges", "unit", "explanation", "caution", "source"}


def test_core_item_coverage():
    # 핵심 항목 10개 이상 확보
    assert len(reference_dict.REFERENCE) >= 10


def test_entry_schema_consistency():
    # 모든 항목이 필수 키 보유
    for name, entry in reference_dict.REFERENCE.items():
        assert _REQUIRED_KEYS <= set(entry), f"{name} 필수 키 누락"
        # ranges 는 (하한, 상한) 튜플
        for rng in entry["ranges"].values():
            assert len(rng) == 2 and rng[0] <= rng[1], f"{name} 범위 오류"


def test_sex_specific_gtp():
    # 감마지티피 - 동일 값이 성별에 따라 다른 판정
    assert classification.classify("감마지티피", 50, "male") == Flag.NORMAL
    assert classification.classify("감마지티피", 50, "female") != Flag.NORMAL


def test_sex_specific_creatinine():
    # 크레아티닌 - 남성 정상, 여성 범위 초과
    assert classification.classify("크레아티닌", 1.3, "male") == Flag.NORMAL
    assert classification.classify("크레아티닌", 1.3, "female") != Flag.NORMAL


def test_hdl_low_is_flagged():
    # HDL 은 낮을수록 위험 - 하한 미만 플래그
    assert classification.classify("HDL 콜레스테롤", 30, "male") != Flag.NORMAL


def test_panic_potassium():
    # 칼륨 응급 수치 - 패닉 감지 및 응급 플래그
    assert panic_values.check_panic("칼륨", 6.8) is not None
    assert classification.classify("칼륨", 6.8, "male") == Flag.EMERGENCY


def test_panic_sodium_both_directions():
    # 나트륨 저·고 양방향 패닉 감지
    assert panic_values.check_panic("나트륨", 118) is not None
    assert panic_values.check_panic("나트륨", 165) is not None
    assert panic_values.check_panic("나트륨", 140) is None
