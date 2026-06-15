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
