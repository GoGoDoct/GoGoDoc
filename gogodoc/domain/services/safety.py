"""안전 가드레일 - 과잉표현 필터, 추적 항목, 면책, 응급 안내 (순수 도메인 규칙)"""

import re

from gogodoc.domain.models import InterpretedItem, FinalReport, Flag, GuideNote
from gogodoc.domain.reference import panic_values, category_guide
from gogodoc.domain.policy import DISCLAIMER

# 진단 단정 과잉표현 - 후처리 차단 대상
_BANNED_PATTERNS = [
    (re.compile(r"암입니다|암이다|암으로"), "추적 관찰이 필요한 소견으로"),
    (re.compile(r"병입니다|질병입니다|확실히"), "주의가 필요한 항목으로"),
    (re.compile(r"진단"), "참고 소견"),
]

# 추적 권장 대상 플래그
_TRACKING_FLAGS = (Flag.CAUTION, Flag.ABNORMAL, Flag.EMERGENCY)


def _filter_expression(text: str) -> str:
    """과잉·단정 표현 필터링"""
    for pattern, replacement in _BANNED_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


def sanitize_text(text: str) -> str:
    """외부 생성 텍스트(종합 요약 등) 과잉표현 필터 - summarize 와 동일 규칙"""
    return _filter_expression(text)


def _build_lifestyle_guide(interpreted: list[InterpretedItem]) -> list[GuideNote]:
    """플래그된 항목의 카테고리별 생활 가이드 수집 - 카테고리 중복 제거 (결정적, 근거 그대로)"""
    seen: set[str] = set()
    guides: list[GuideNote] = []
    for item in interpreted:
        if item.flag not in _TRACKING_FLAGS:
            continue
        category = category_guide.category_of(item.canonical_name)
        if not category or category in seen:
            continue
        g = category_guide.guide_for(category)
        if not g:
            continue
        seen.add(category)
        guides.append(
            GuideNote(
                category=category,
                lifestyle=g["lifestyle"],
                tracking=g["tracking"],
                department=g["department"],
                source=g["source"],
            )
        )
    return guides


def summarize(interpreted: list[InterpretedItem]) -> FinalReport:
    """단계 4 - 과잉표현 필터, 추적·응급 수집, 생활 가이드, 면책 삽입"""
    tracking: list[str] = []
    emergencies: list[str] = []

    for item in interpreted:
        # 과잉표현 필터링
        item.explanation = _filter_expression(item.explanation)

        # 추적 권장 항목 수집
        if item.flag in _TRACKING_FLAGS:
            tracking.append(item.canonical_name)

        # 응급 이상치 내원 안내 수집
        alert = panic_values.check_panic(item.canonical_name, item.value)
        if alert:
            emergencies.append(alert)

    return FinalReport(
        items=interpreted,
        tracking_items=tracking,
        emergency_alerts=emergencies,
        lifestyle_guide=_build_lifestyle_guide(interpreted),
        disclaimer=DISCLAIMER,
    )
