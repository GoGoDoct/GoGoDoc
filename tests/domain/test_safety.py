"""안전 가드레일 단위 테스트"""

from gogodoc.domain.models import InterpretedItem, Flag
from gogodoc.domain.services import safety


def _item(name, value, flag, explanation):
    return InterpretedItem(
        canonical_name=name,
        raw_name=name,
        value=value,
        flag=flag,
        explanation=explanation,
    )


def test_filters_diagnosis_term():
    # 진단 단정 표현 후처리 필터링
    report = safety.summarize([_item("ALT", 200, Flag.ABNORMAL, "이것은 암입니다")])
    assert "암입니다" not in report.items[0].explanation


def test_filters_paraphrased_assertions():
    # 패러프레이즈된 단정도 중화 (악성·환자라벨·확정부사·질환명단정)
    for text, banned in [
        ("악성 종양이 의심됩니다", "악성"),
        ("당뇨 환자입니다", "환자입니다"),
        ("당뇨병이 확실합니다", "확실합니다"),
        ("사실상 고혈압입니다", "고혈압입니다"),
        ("분명히 당뇨입니다", "분명히"),
    ]:
        assert banned not in safety.sanitize_text(text), text


def test_does_not_overfilter_legit_text():
    # 정상·헤지 표현은 그대로 (오차단 금지)
    for text in [
        "정상 범위입니다",
        "경계 수치로 추적 관찰이 권장됩니다",
        "당뇨 전단계로 보입니다",
        "공복혈당장애가 의심됩니다",
        "수치가 다소 높습니다",
    ]:
        assert safety.sanitize_text(text) == text, text


def test_disclaimer_enforced():
    # 면책 문구 강제 삽입
    report = safety.summarize([_item("ALT", 20, Flag.NORMAL, "정상입니다")])
    assert report.disclaimer


def test_tracking_collected():
    # 주의·이상·응급 항목만 추적 수집
    report = safety.summarize(
        [
            _item("ALT", 200, Flag.ABNORMAL, "x"),
            _item("AST", 20, Flag.NORMAL, "y"),
        ]
    )
    assert report.tracking_items == ["ALT"]


def test_emergency_alert_collected():
    # 패닉 밸류 항목 - 내원 안내 수집
    report = safety.summarize([_item("공복혈당", 600, Flag.EMERGENCY, "z")])
    assert len(report.emergency_alerts) == 1


def test_lifestyle_guide_for_flagged_deduped():
    # 플래그 항목의 카테고리별 생활 가이드 - 같은 카테고리 중복 제거, 순서 유지
    report = safety.summarize(
        [
            _item("ALT", 200, Flag.ABNORMAL, "x"),
            _item("AST", 100, Flag.CAUTION, "y"),  # ALT 와 같은 간기능 - 1개로
            _item("총콜레스테롤", 300, Flag.ABNORMAL, "z"),
        ]
    )
    assert [g.category for g in report.lifestyle_guide] == ["간기능", "지질"]
    assert all(g.department and g.source for g in report.lifestyle_guide)


def test_no_lifestyle_guide_when_all_normal():
    # 정상만 있으면 생활 가이드 없음
    report = safety.summarize([_item("ALT", 20, Flag.NORMAL, "정상")])
    assert report.lifestyle_guide == []
