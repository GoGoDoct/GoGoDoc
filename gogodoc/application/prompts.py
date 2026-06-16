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


# F-007 - 챗봇 RAG 답변 생성 (공인 출처 근거 고정)
CHAT_ANSWER_SYSTEM = (
    "너는 건강검진 결과 챗봇이다. 사용자의 검진 결과와 아래 제공된 공인 출처 근거 안에서만 답한다. "
    + GUARDRAIL_INSTRUCTIONS
    + " 근거에 없는 수치·진단명·약물·식단은 만들어내지 않는다."
    + " 진단 단정이나 약 처방·복용 판단은 하지 않고, 필요하면 전문의 상담을 권한다."
    + " 답변 끝에 사용한 출처 기관을 밝히고, 참고용임을 한 문장으로 안내한다."
    + " 4-6문장의 쉬운 한국어로 답한다."
)


def build_chat_answer_user(question: str, grounding: dict) -> str:
    """챗봇 답변 사용자 프롬프트 - 질문 + 검진결과·근거카드·생활가이드 주입 (근거 고정)"""
    lines = [f"[질문] {question}"]
    items = grounding.get("items", [])
    if items:
        lines.append("[관련 검진 항목 근거]")
        for it in items:
            mine = f" / 내 수치 {it['value']} ({it['flag']})" if it.get("in_report") else ""
            lines.append(
                f"- {it['name']}: {it['explanation']} / 주의: {it['caution']} / 정상범위 {it['range']}"
                f"{mine} (출처 {it['source']})"
            )
    guides = grounding.get("guides", [])
    if guides:
        lines.append("[생활 가이드 근거]")
        for g in guides:
            lines.append(
                f"- {g['category']}: {g['lifestyle']} / 추적: {g['tracking']} / 진료과: {g['department']} (출처 {g['source']})"
            )
    lines.append("위 근거만 사용해 질문에 쉽게 답하라. 근거가 부족하면 솔직히 말하고 전문의 상담을 권하라.")
    return "\n".join(lines)


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


# 평가 - 생성 답변 근거성·환각 심판 (LLM-as-judge, 결정적 JSON)
JUDGE_SYSTEM = (
    "너는 의료 설명문의 사실성을 검증하는 엄격한 채점자다. "
    "주어진 [근거] 안의 정보만을 기준으로 [답변]을 평가한다. "
    "groundedness: 답변의 모든 핵심 주장이 근거로 뒷받침되면 1, 일부만이면 0.5, 거의 아니면 0. "
    "major_hallucination: 근거에 없거나 근거와 모순되는 의학적 주장(수치·진단·치료)이 있으면 true, 없으면 false. "
    '출력은 JSON 한 줄만: {"groundedness": <0|0.5|1>, "major_hallucination": <true|false>}'
)


def build_judge_user(answer: str, grounding: dict, reference_range=None, value=None, status=None) -> str:
    """심판 사용자 프롬프트 - 근거(해설·주의·출처·정상범위·측정값·판정상태) 대비 답변 검증

    정상범위·측정값·판정상태도 근거에 포함 - 답변이 인용하는 정당한 범위·측정 숫자나
    시스템 판정(응급=즉시 내원)을 환각으로 오판 방지
    """
    lines = [
        "[근거]",
        f"- 해설: {grounding.get('explanation')}",
        f"- 주의: {grounding.get('caution')}",
        f"- 출처: {grounding.get('source')}",
    ]
    if reference_range is not None:
        lines.append(f"- 정상범위: {reference_range}")
    if value is not None:
        lines.append(f"- 측정값: {value}")
    if status is not None:
        lines.append(f"- 판정 상태: {status} (응급이면 즉시 내원 안내가 정당함)")
    lines += ["", "[답변]", answer]
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
