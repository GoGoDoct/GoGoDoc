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


def test_variant_synonyms_resolved():
    # 검진지 변형 표기 - 동의어 등록으로 정확 매칭 (오적중·known_gap 해소)
    cases = {
        "혈색소": "헤모글로빈",
        "Hb": "헤모글로빈",  # 과거 fuzzy 로 당화혈색소 오적중하던 케이스
        "γ-GTP": "감마지티피",
        "TG": "중성지방",
        "SBP": "수축기혈압",
        "사구체여과율": "eGFR",
    }
    for raw, expected in cases.items():
        canonical, score, matched = normalization.canonicalize(raw)
        assert canonical == expected, f"{raw} -> {canonical} (기대 {expected})"
        assert matched is True and score == 100.0


def test_unknown_not_false_matched():
    # 미수록 항목은 여전히 미매칭이어야 (동의어 확장이 오적중 유발 안 함)
    for raw in ("TSH", "백혈구", "갑상선"):
        canonical, _, matched = normalization.canonicalize(raw)
        assert matched is False, f"{raw} 가 {canonical} 로 오매칭됨"
