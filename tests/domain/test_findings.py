"""정성 소견 KB·복합검사 분해 테스트 (순수 도메인)"""

from gogodoc.domain.reference import findings
from gogodoc.domain.services import composite
from gogodoc.domain.services.classification import classify_finding
from gogodoc.domain.models import Flag


def test_urine_protein_grades():
    assert classify_finding("요단백", "음성") == Flag.NORMAL
    assert classify_finding("요단백", "약양성(±)") == Flag.CAUTION
    assert classify_finding("요단백", "양성(2+)") == Flag.ABNORMAL


def test_endoscopy_findings():
    assert classify_finding("위내시경", "만성위염") == Flag.CAUTION
    assert classify_finding("위내시경", "위궤양") == Flag.ABNORMAL
    assert classify_finding("대장내시경", "대장용종") == Flag.ABNORMAL


def test_ultrasound_and_hbv():
    assert classify_finding("복부초음파", "지방간") == Flag.CAUTION
    assert classify_finding("복부초음파", "담낭용종") == Flag.CAUTION
    assert classify_finding("B형간염 표면항원", "양성") == Flag.ABNORMAL
    assert classify_finding("B형간염 표면항원", "음성") == Flag.NORMAL


def test_specific_keyword_beats_general():
    # 약양성(±)은 '양성' 포괄어보다 먼저 매칭되어야 함
    assert classify_finding("요단백", "약양성(±)") == Flag.CAUTION


def test_finding_card_has_grounding():
    card = findings.lookup_finding("복부초음파", "지방간")
    assert card["flag"] == "caution"
    assert card["explanation"] and card["caution"] and card["source"]


def test_non_finding_item_returns_none():
    # 수치 항목·미매칭 소견은 None (상위 폴백)
    assert classify_finding("공복혈당", "120") is None
    assert classify_finding("위내시경", "알수없는소견") is None


def test_composite_split_and_aliases():
    parsed = composite.parse_composite("혈압150/총콜250/중성지방280")
    assert ("수축기혈압", 150.0) in parsed
    assert ("총콜레스테롤", 250.0) in parsed
    assert ("중성지방", 280.0) in parsed
    assert composite.is_composite("공복혈당380/혈압200")
    assert not composite.is_composite("120")


def test_composite_emergency_member():
    # 복합검사에 응급 수치 포함 시 구성 분류로 응급 검출 가능
    from gogodoc.domain.services.classification import classify
    parsed = dict(composite.parse_composite("공복혈당380/혈압200"))
    assert classify("공복혈당", parsed["공복혈당"], "male", 45) == Flag.EMERGENCY
