"""카테고리 생활 가이드 단위 테스트 - 항목→카테고리→가이드 연결 검증"""

from gogodoc.domain.reference import category_guide, reference_dict


def test_category_of_known():
    assert category_guide.category_of("ALT") == "간기능"
    assert category_guide.category_of("공복혈당") == "혈당"
    assert category_guide.category_of("총콜레스테롤") == "지질"


def test_category_of_unknown():
    assert category_guide.category_of("없는항목xyz") is None


def test_guide_has_required_fields():
    g = category_guide.guide_for("간기능")
    assert g is not None
    for key in ("lifestyle", "tracking", "department", "source"):
        assert g.get(key), f"필드 누락: {key}"


def test_every_reference_item_maps_to_guide():
    # 모든 표준 항목이 카테고리·가이드로 연결되어야 종합 요약에서 누락 없음
    for name in reference_dict.REFERENCE:
        cat = category_guide.category_of(name)
        assert cat, f"카테고리 미매핑: {name}"
        assert category_guide.guide_for(cat), f"가이드 미존재: {cat}"
