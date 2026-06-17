"""F-007 챗봇 질문 스코프 판정 - 허용/비허용 규칙 (순수 도메인)

허용: 검진 수치 설명, 일반 생활습관, 진료과 안내
비허용: 진단 단정, 처방·복약, 수술 등 의료행위 -> 전문의 상담 라우팅

안전 원칙 (의료법 리스크 차단)
- 규칙은 고정밀 하드 차단 - 명백한 진단·처방·복약만 BLOCKED 로 단정
- 애매한 질문은 None 반환 -> 상위(LLM 분류)에 위임, 거기서 모호하면 비허용(보수적)
- 목표: 위험질문 통과율 0 (false negative 최소화)
"""

import re

from gogodoc.domain.models import QuestionType, Scope, ScopeDecision

_QUESTION_TYPE_SCOPE = {
    QuestionType.CHECKUP_EXPLANATION: Scope.ALLOWED,
    QuestionType.CHECKUP_SUMMARY: Scope.ALLOWED,
    QuestionType.LIFESTYLE_GENERAL: Scope.ALLOWED,
    QuestionType.DEPARTMENT_GUIDE: Scope.ALLOWED,
    QuestionType.DIAGNOSIS_REQUEST: Scope.BLOCKED,
    QuestionType.PRESCRIPTION_REQUEST: Scope.BLOCKED,
    QuestionType.DOSAGE_REQUEST: Scope.BLOCKED,
    QuestionType.PROCEDURE_REQUEST: Scope.BLOCKED,
    QuestionType.EMERGENCY_SYMPTOM: Scope.BLOCKED,
    QuestionType.SELF_HARM_CRISIS: Scope.BLOCKED,
    QuestionType.SYMPTOM_NON_EMERGENCY: Scope.BLOCKED,
    QuestionType.OUT_OF_SCOPE_NONMEDICAL: Scope.BLOCKED,
    QuestionType.APP_HELP: Scope.BLOCKED,
    QuestionType.UNSUPPORTED: Scope.BLOCKED,
    QuestionType.UNKNOWN: Scope.BLOCKED,
}

# 규칙 기반 하드 라우팅 패턴 - 위험도가 높은 유형부터 평가
_RULE_PATTERNS: list[tuple[QuestionType, str, re.Pattern[str]]] = [
    (
        QuestionType.SELF_HARM_CRISIS,
        "self_harm_rule",
        re.compile(r"죽고\s*싶|자살|자해|극단적\s*선택|목숨\s*(끊|끊고)|약을\s*많이\s*먹"),
    ),
    (
        QuestionType.EMERGENCY_SYMPTOM,
        "emergency_rule",
        re.compile(
            r"가슴.*(통증|아프|답답|조이|압박)|흉통|숨이?\s*(차|막히|안\s*쉬|가쁘)|호흡\s*곤란|"
            r"한쪽.*(마비|힘이?\s*안|감각)|말이?\s*어눌|의식.*(잃|저하|없)|실신|경련|"
            r"심한\s*출혈|극심한\s*두통|갑자기.*두통|얼굴.*마비|팔.*마비"
        ),
    ),
    (
        QuestionType.DOSAGE_REQUEST,
        "dosage_rule",
        re.compile(r"용량|몇\s*(알|정|mg|밀리그램)|증량|감량"),
    ),
    (
        QuestionType.PRESCRIPTION_REQUEST,
        "prescription_rule",
        re.compile(
            r"무슨\s*약|어떤\s*약|약\s*(을|를|은|이|좀)?\s*(먹|복용|드시|바꾸|바꿔|끊|줄여|늘려)|"
            r"(스타틴|메트포민|혈압약|고지혈증약|당뇨약).*(먹|복용|시작|끊|바꾸)|처방|복용|투약"
        ),
    ),
    (
        QuestionType.DIAGNOSIS_REQUEST,
        "diagnosis_rule",
        re.compile(
            r"(암|종양|간암|위암|대장암|간경화|당뇨병|고혈압|갑상선암|신부전)\s*"
            r"(이에요|이예요|인가요|입니까|맞나요|인지|일까요|이라는|진단)|"
            r"무슨\s*병|병명|진단(해|받|명|을|이)|확진"
        ),
    ),
    (
        QuestionType.PROCEDURE_REQUEST,
        "procedure_rule",
        re.compile(r"수술|시술|항암|입원|주사\s*(맞|놓)"),
    ),
    (
        QuestionType.UNSUPPORTED,
        "unsupported_rule",
        re.compile(r"작년|지난\s*번|이전\s*검진|추세|비교|근처\s*병원|병원\s*추천"),
    ),
    (
        QuestionType.APP_HELP,
        "app_help_rule",
        re.compile(r"업로드|로그인|회원가입|PDF|결과\s*(어디|보기|확인)|사용법"),
    ),
    (
        QuestionType.OUT_OF_SCOPE_NONMEDICAL,
        "out_of_scope_rule",
        re.compile(r"배고파|날씨|주식|로또|영화\s*추천|맛집|여행|환율|코딩"),
    ),
]

_SYMPTOM_HINT = re.compile(r"(아파|통증|쑤셔|어지러|메스꺼|토할|열이\s*나|기침|설사|허리|배가\s*아)")

# 전문의 상담 라우팅 안내 (비허용 질문 응답)
ROUTING_MESSAGE = (
    "이 질문은 진단·처방·복약에 해당할 수 있어 정확한 답변을 드리기 어렵습니다. "
    "정확한 판단은 전문의와 상담하시길 권장합니다."
)

ROUTING_MESSAGES = {
    QuestionType.EMERGENCY_SYMPTOM: (
        "말씀하신 증상은 응급 상황일 수 있습니다. 지금 바로 119에 연락하거나 "
        "가까운 응급실로 이동하세요."
    ),
    QuestionType.SELF_HARM_CRISIS: (
        "지금 안전이 가장 중요합니다. 혼자 있지 말고 즉시 119 또는 112에 연락하세요. "
        "자살예방상담전화 109에서도 바로 도움을 받을 수 있습니다."
    ),
    QuestionType.DIAGNOSIS_REQUEST: (
        "이 질문은 질병 여부를 확정하는 진단 요청에 해당할 수 있어 답변하기 어렵습니다. "
        "검진 결과지를 지참해 의료진과 상담하시길 권장합니다."
    ),
    QuestionType.PRESCRIPTION_REQUEST: (
        "약 처방이나 복용 여부는 개인 상태와 병력 확인이 필요해 챗봇이 판단할 수 없습니다. "
        "담당 전문의 또는 약사와 상담하시길 권장합니다."
    ),
    QuestionType.DOSAGE_REQUEST: (
        "약물 용량, 증량, 감량 판단은 챗봇이 안내할 수 없습니다. "
        "처방한 전문의 또는 약사와 상담하시길 권장합니다."
    ),
    QuestionType.PROCEDURE_REQUEST: (
        "수술·시술·입원 여부는 의료진의 직접 진료가 필요한 판단입니다. "
        "검진 결과와 증상을 가지고 전문의와 상담하세요."
    ),
    QuestionType.SYMPTOM_NON_EMERGENCY: (
        "증상의 원인은 건강검진 결과만으로 판단할 수 없습니다. 증상이 지속되거나 악화되면 "
        "의료기관에서 진료를 받으세요. 갑작스러운 흉통, 호흡곤란, 마비, 실신이 있으면 즉시 119에 연락하세요."
    ),
    QuestionType.OUT_OF_SCOPE_NONMEDICAL: (
        "저는 건강검진 결과 해석을 돕는 챗봇입니다. 검진 수치의 의미, 생활습관 관리, "
        "진료과 상담 방향에 대해 질문해 주세요."
    ),
    QuestionType.APP_HELP: (
        "검진 결과 업로드와 결과 확인은 앱 화면의 업로드·기록 메뉴에서 진행할 수 있습니다. "
        "현재 챗봇은 검진 결과 해석 질문을 중심으로 답변합니다."
    ),
    QuestionType.UNSUPPORTED: (
        "현재 챗봇은 최신 검진 결과 1건을 기준으로 답변합니다. 과거 결과와의 추세 비교나 "
        "실제 병원 추천은 아직 지원하지 않습니다."
    ),
    QuestionType.UNKNOWN: (
        "질문 의도를 명확히 판단하기 어렵습니다. 검진 항목명이나 수치를 포함해 다시 질문해 주세요."
    ),
}


def scope_for_question_type(question_type: QuestionType) -> Scope:
    """질문 유형별 답변 생성 가능 여부 반환"""
    return _QUESTION_TYPE_SCOPE.get(question_type, Scope.BLOCKED)


def routing_message(question_type: QuestionType) -> str:
    """질문 유형별 라우팅 안내 문구 반환"""
    return ROUTING_MESSAGES.get(question_type, ROUTING_MESSAGE)


def classify_rule_detail(question: str) -> ScopeDecision | None:
    """규칙 기반 세부 라우팅 - 명확한 유형이면 결정, 아니면 None(LLM 위임)"""
    text = (question or "").strip()
    if not text:
        return ScopeDecision(
            scope=Scope.BLOCKED,
            routed=True,
            reason="rule",
            question_type=QuestionType.UNKNOWN,
            route_reason="empty_question",
        )

    for question_type, route_reason, pattern in _RULE_PATTERNS:
        if pattern.search(text):
            return ScopeDecision(
                scope=scope_for_question_type(question_type),
                routed=scope_for_question_type(question_type) == Scope.BLOCKED,
                reason="rule",
                question_type=question_type,
                route_reason=route_reason,
            )

    if _SYMPTOM_HINT.search(text):
        return ScopeDecision(
            scope=Scope.BLOCKED,
            routed=True,
            reason="rule",
            question_type=QuestionType.SYMPTOM_NON_EMERGENCY,
            route_reason="symptom_rule",
        )

    return None


def classify_rule(question: str) -> Scope | None:
    """규칙 기반 하드 차단 - 명백한 비허용이면 BLOCKED, 아니면 None(LLM 위임)"""
    decision = classify_rule_detail(question)
    return decision.scope if decision is not None else None
