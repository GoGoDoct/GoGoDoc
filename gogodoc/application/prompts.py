"""LLM 프롬프트 - 구조화 및 해석 (가드레일은 도메인 정책에서 주입)"""

from gogodoc.domain.models import MatchedItem, UserProfile
from gogodoc.domain.policy import GUARDRAIL_INSTRUCTIONS

# 단계 1 - 구조화 시스템 프롬프트
STRUCTURING_SYSTEM = (
    "너는 건강검진 결과지 텍스트를 구조화하는 추출기다. "
    "검사 항목을 JSON 배열로만 출력한다. "
    '각 원소는 {"name", "value", "unit", "reference_range"} 형식이고 '
    "값이 없으면 null 을 사용한다. "
    "설명·코드블록 없이 JSON 만 출력한다."
)

# 단계 3 - 해석 시스템 프롬프트 (도메인 가드레일 결합)
INTERPRET_SYSTEM = (
    "너는 건강검진 결과를 일반인에게 쉽게 풀어주는 도우미다. "
    + GUARDRAIL_INSTRUCTIONS
    + " 제공된 근거에 없는 수치·진단명·치료법은 언급하지 않는다."
    + " 3-5문장의 쉬운 한국어로 답한다."
)


def build_interpret_user(
    item: MatchedItem, profile: UserProfile, grounding: dict, reference_range
) -> str:
    """항목별 근거 포함 사용자 프롬프트 구성"""
    return (
        f"[사용자] 성별 {profile.sex.value}, 나이 {profile.age}\n"
        f"[항목] {item.canonical_name}\n"
        f"[측정값] {item.value} {item.unit or ''}\n"
        f"[상태] {item.flag.value}\n"
        f"[정상범위] {reference_range}\n"
        f"[해설 근거] {grounding.get('explanation')}\n"
        f"[주의사항] {grounding.get('caution')}\n"
        f"[출처] {grounding.get('source')}\n"
        "위 근거만 사용해 쉬운 설명을 작성하라."
    )
