"""정상범위 판정 단위 테스트 (성별·나이 반영)"""

from gogodoc.domain.models import Flag
from gogodoc.domain.services import classification
from gogodoc.domain.reference import panic_values


def test_normal():
    # 정상범위 내 - 정상
    assert classification.classify("ALT", 20, "male", 40) == Flag.NORMAL


def test_abnormal():
    # 정상범위 크게 초과 - 이상
    assert classification.classify("ALT", 200, "male", 40) == Flag.ABNORMAL


def test_emergency_priority():
    # 패닉 밸류 - 응급 우선
    assert classification.classify("공복혈당", 600, "male", 40) == Flag.EMERGENCY


def test_unknown_value():
    # 값 없음 - 판정 불가
    assert classification.classify("ALT", None, "male", 40) == Flag.UNKNOWN


def test_pediatric_out_of_scope():
    # 성인 기준만 제공 - 소아 나이는 판정 불가
    assert classification.classify("ALT", 20, "male", 10) == Flag.UNKNOWN


def test_panic_check():
    # 패닉 밸류 직접 검증
    assert panic_values.check_panic("공복혈당", 600) is not None
    assert panic_values.check_panic("공복혈당", 90) is None
