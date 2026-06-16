"""LLM 프롬프트 - 구조화 및 해석 (가드레일은 도메인 정책에서 주입)"""

from gogodoc.domain.models import MatchedItem, UserProfile, Flag
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


# F-007 - 챗봇 질문 스코프 분류 (허용/비허용, 보수적)
CHAT_SCOPE_SYSTEM = (
    "너는 건강검진 결과 챗봇의 질문 분류기다. 사용자 질문을 둘 중 하나로만 분류한다. "
    "허용: 검진 수치·항목 의미 설명, 일반적인 생활습관·식이·운동 안내, 어느 진료과를 가야 하는지 안내. "
    "비허용: 특정 질환의 진단 단정, 약 처방·복용·용량, 수술·시술 등 의료행위 판단. "
    "판단이 모호하면 반드시 '비허용'으로 분류한다. "
    "출력은 '허용' 또는 '비허용' 한 단어만."
)


# F-007 - 챗봇 답변 생성 (최신 검진 결과 컨텍스트 + 근거 고정)
CHAT_ANSWER_SYSTEM = (
    "너는 건강검진 결과를 바탕으로 후속 질문에 답하는 제한형 도우미다. "
    + GUARDRAIL_INSTRUCTIONS
    + " 제공된 검진 항목, 기존 해설, 생활 가이드 근거 안에서만 답한다. "
    + "진단 확정, 처방, 약 복용 여부, 약물 용량, 수술·시술 판단은 하지 않는다. "
    + "2-5문장의 쉬운 한국어로 답한다."
)


# 단계 5 - 종합 요약 시스템 프롬프트 (직장인용, 도메인 가드레일 결합)
SUMMARY_SYSTEM = (
    "너는 건강검진 결과 전체를 직장인이 이해하기 쉽게 요약해 주는 도우미다. "
    + GUARDRAIL_INSTRUCTIONS
    + " 제공된 항목·생활 가이드 근거에 없는 수치·진단명·식단·약물은 추가하지 않는다."
    + " 응급 안내가 있으면 가장 먼저 즉시 내원을 안내한다."
    + " 4-7문장의 쉬운 한국어로, 신경 쓸 항목과 생활 관리·추적 중심으로 답한다."
)


def build_summary_user(report, profile: UserProfile) -> str:
    """종합 요약 사용자 프롬프트 - 플래그 항목 + 카테고리 생활 가이드 주입 (근거 고정)"""
    flagged = [it for it in report.items if it.flag in (Flag.CAUTION, Flag.ABNORMAL, Flag.EMERGENCY)]
    normal_n = sum(1 for it in report.items if it.flag == Flag.NORMAL)

    lines = [f"[사용자] 성별 {profile.sex.value}, 나이 {profile.age}"]
    lines.append(
        "[응급] " + ("; ".join(report.emergency_alerts) if report.emergency_alerts else "없음")
    )
    if flagged:
        lines.append("[주의·이상 항목]")
        for it in flagged:
            lines.append(f"- {it.canonical_name} ({it.flag.value}) {it.value} {it.unit or ''}")
    lines.append(f"[정상 항목 수] {normal_n}")
    if report.lifestyle_guide:
        lines.append("[카테고리별 생활 가이드]")
        for g in report.lifestyle_guide:
            lines.append(
                f"- {g.category}: {g.lifestyle} / 추적: {g.tracking} / 진료과: {g.department} (출처 {g.source})"
            )
    lines.append("위 근거만 사용해 직장인이 이해하기 쉽게 종합 요약을 작성하라.")
    return "\n".join(lines)


def build_interpret_user(
    item: MatchedItem, profile: UserProfile, grounding: dict, reference_range
) -> str:
    """항목별 근거 포함 사용자 프롬프트 구성 - 응급 항목은 긴급 내원 톤 지시"""
    lines = [
        f"[사용자] 성별 {profile.sex.value}, 나이 {profile.age}",
        f"[항목] {item.canonical_name}",
        f"[측정값] {item.value} {item.unit or ''}",
        f"[상태] {item.flag.value}",
        f"[정상범위] {reference_range}",
        f"[해설 근거] {grounding.get('explanation')}",
        f"[주의사항] {grounding.get('caution')}",
        f"[출처] {grounding.get('source')}",
    ]
    # 응급(패닉) 항목 - 추적 관찰이 아니라 즉시 내원 안내 강제
    if item.flag == Flag.EMERGENCY:
        lines.append(
            "이 수치는 응급(패닉) 수준이다. 추적 관찰이 아니라 "
            "즉시 의료기관에 내원해야 함을 첫 문장에서 분명히 안내하라."
        )
    lines.append("위 근거만 사용해 쉬운 설명을 작성하라.")
    return "\n".join(lines)
