"""임상 밴드 분류 테스트 - 팀 골든 컷오프 정합 (순수 도메인)"""

from gogodoc.domain.services.classification import classify
from gogodoc.domain.models import Flag


def test_glucose_bands():
    assert classify("공복혈당", 95, "male", 45) == Flag.NORMAL
    assert classify("공복혈당", 118, "male", 45) == Flag.CAUTION
    assert classify("공복혈당", 140, "male", 45) == Flag.ABNORMAL
    assert classify("공복혈당", 320, "male", 45) == Flag.EMERGENCY  # 팀 응급 컷오프


def test_bp_emergency():
    assert classify("수축기혈압", 195, "male", 45) == Flag.EMERGENCY
    assert classify("이완기혈압", 125, "male", 45) == Flag.EMERGENCY


def test_cholesterol_abnormal_band():
    # 편차모델은 주의로 빠뜨리던 구간 - 임상 밴드로 이상
    assert classify("총콜레스테롤", 260, "male", 45) == Flag.ABNORMAL
    assert classify("LDL 콜레스테롤", 160, "male", 45) == Flag.ABNORMAL


def test_liver_caution_band():
    # 편차모델은 이상으로 과경고하던 구간 - 임상 밴드로 주의
    assert classify("AST", 65, "male", 45) == Flag.CAUTION
    assert classify("AST", 95, "male", 45) == Flag.ABNORMAL
    assert classify("ALT", 70, "male", 45) == Flag.CAUTION


def test_low_bad_items():
    # HDL·eGFR·헤모글로빈은 낮을수록 나쁨
    assert classify("HDL 콜레스테롤", 28, "male", 45) == Flag.ABNORMAL
    assert classify("eGFR", 45, "male", 45) == Flag.ABNORMAL
    assert classify("eGFR", 75, "male", 45) == Flag.CAUTION


def test_tumor_markers_cap_at_caution():
    # 종양표지자는 상승해도 주의까지만 (단독 진단 불가)
    assert classify("CEA", 8.0, "male", 55) == Flag.CAUTION
    assert classify("PSA", 6.5, "male", 55) == Flag.CAUTION


def test_severe_value_emergency_preserved():
    # 심한 신부전·빈혈 응급 보존
    assert classify("크레아티닌", 8.0, "male", 60) == Flag.EMERGENCY
    assert classify("헤모글로빈", 6.5, "female", 40) == Flag.EMERGENCY
