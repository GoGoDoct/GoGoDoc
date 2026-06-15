"""항목명 정규화 단위 테스트"""

from gogodoc.domain.services import normalization


def test_direct_synonym():
    # GPT -> ALT 동의어 직접 매칭
    canonical, score, matched = normalization.canonicalize("GPT")
    assert canonical == "ALT"
    assert matched is True
    assert score == 100.0


def test_fuzzy_fallback():
    # 오타 항목명 rapidfuzz fallback 매칭
    canonical, _, matched = normalization.canonicalize("공복혈당치")
    assert canonical == "공복혈당"
    assert matched is True


def test_unmatched():
    # 미등록 항목명 - 원본 유지 및 미매칭
    canonical, score, matched = normalization.canonicalize("알수없는항목xyz")
    assert canonical == "알수없는항목xyz"
    assert matched is False
    assert score == 0.0
