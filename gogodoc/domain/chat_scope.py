"""F-007 챗봇 질문 스코프 판정 - 허용/비허용 규칙 (순수 도메인)

허용: 검진 수치 설명, 일반 생활습관, 진료과 안내
비허용: 진단 단정, 처방·복약, 수술 등 의료행위 -> 전문의 상담 라우팅

안전 원칙 (의료법 리스크 차단)
- 규칙은 고정밀 하드 차단 - 명백한 진단·처방·복약만 BLOCKED 로 단정
- 애매한 질문은 None 반환 -> 상위(LLM 분류)에 위임, 거기서 모호하면 비허용(보수적)
- 목표: 위험질문 통과율 0 (false negative 최소화)
"""

import re

from rapidfuzz import fuzz

from gogodoc.domain.models import QuestionType, Scope, ScopeDecision
from gogodoc.domain.reference import reference_dict
from gogodoc.domain.reference.synonyms import SYNONYMS

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
            r"가슴.*(뻐근|불편)|"
            r"숨\s*쉬기\s*(힘들|어렵)|숨\s*못\s*쉬|숨이\s*안\s*쉬|"
            r"한쪽.*(마비|힘이?\s*안|감각)|말이?\s*어눌|의식.*(잃|저하|없)|실신|경련|"
            r"심한\s*출혈|극심한\s*두통|갑자기.*두통|얼굴.*마비|팔.*마비|"
            r"(아기|아이|소아|영아).{0,20}(축\s*처지|소변.{0,8}(거의\s*없|줄)|물.{0,8}못\s*마|반복.{0,8}구토)"
        ),
    ),
    (
        QuestionType.DOSAGE_REQUEST,
        "dosage_rule",
        re.compile(
            r"용량|몇\s*(알|정)|증량|감량|"
            r"((?<![가-힣])약(?!간)|스타틴|메트포민|혈압약|고지혈증약|당뇨약|치료제).{0,20}몇\s*(mg|밀리그램)|"
            r"몇\s*(mg|밀리그램).{0,20}(먹|복용|드시|처방)"
        ),
    ),
    (
        QuestionType.PRESCRIPTION_REQUEST,
        "prescription_rule",
        re.compile(
            r"무슨\s*약|어떤\s*약|(?<![가-힣])약\s*(을|를|은|이|좀)?\s*(먹|복용|드시|바꾸|바꿔|끊|줄여|늘려)|"
            r"(스타틴|메트포민|혈압약|고지혈증약|당뇨약|아스피린|위고비|마운자로|졸피뎀|알닥톤|타이레놀|한약)"
            r".*(먹|복용|시작|끊|바꾸|추천|계속|같이|병용|중단)|"
            r"(높|낮|이상|초과|미만|수치|검사|검진|결과|이면|라면|나오).{0,28}(?<![가-힣])약(?!간)\s*\??\s*$|"
            r"(스타틴|메트포민|혈압약|고지혈증약|당뇨약|아스피린|위고비|마운자로|졸피뎀|알닥톤|"
            r"타이레놀|한약|철분제|인슐린|통풍약|치료제|약물치료)"
            r"\s*(이|가|은|는|을|를)?\s*\??\s*$|"
            r"(낮추|높이|조절|관리).{0,20}((?<![가-힣])약(?!간)|주사|치료제).{0,12}(뭐|무엇|알려|추천|필요)|"
            r"((?<![가-힣])약(?!간)|주사|치료제|철분제|인슐린|통풍약)\s*(이|가|은|는|을|를)?\s*(뭐|무엇|알려|추천)|"
            r"((?<![가-힣])약(?!간)|주사|치료제|혈압약|당뇨약|고지혈증약|철분제|인슐린|통풍약|약물치료)"
            r".{0,16}(필요|해야|써야|먹어야|맞아야|되나|될까|될까요)|"
            r"(필요|해야|써야|먹어야|맞아야).{0,16}"
            r"((?<![가-힣])약(?!간)|주사|치료제|혈압약|당뇨약|고지혈증약|철분제|인슐린|통풍약|약물치료)|"
            r"(먹|복용).{0,12}(되나요|될까요|괜찮|가능)|"
            r"약\s*추천|치료제\s*추천|추천.*(약|치료제)|처방|복용|투약|병용"
        ),
    ),
    (
        QuestionType.DIAGNOSIS_REQUEST,
        "diagnosis_rule",
        re.compile(
            r"(암|종양|간암|위암|대장암|간경화|당뇨병|고혈압|갑상선암|신부전)\s*"
            r"(이에요|이예요|인가요|입니까|맞나요|인지|일까요|이라는|진단)|"
            r"(당뇨|당뇨병|고혈압|고지혈증|암|종양|간경화|신부전)\s*"
            r"(이야|야|인가|일까|일까요|일\s*가능성|가능성)|"
            r"임신.{0,12}(가능성|인가요|일까요|맞나요)|"
            r"(우울증|불안장애).{0,12}(인가요|일까요|맞나요)|"
            r"무슨\s*병|병명|큰\s*병|위험한\s*상태|진단(해|받|명|을|이)|확진"
        ),
    ),
    (
        QuestionType.UNSUPPORTED,
        "unsupported_rule",
        re.compile(
            r"작년|지난\s*번|이전\s*검진|과거\s*검진|전\s*검진|추세|"
            r"(작년|지난|이전|과거|전\s*검진).*(비교|대비)|근처\s*병원|병원\s*추천|"
            r"비용|가격|보험|실비|싼\s*병원|저렴한\s*병원|"
            r"(스타틴|메트포민|위고비|마운자로|졸피뎀|알닥톤|타이레놀).{0,12}(뭔|무엇|설명|효과)|"
            r"임신\s*중.{0,20}(기준|검사\s*수치|정상\s*범위)"
        ),
    ),
    (
        QuestionType.PROCEDURE_REQUEST,
        "procedure_rule",
        re.compile(
            r"(수술|시술|항암|입원).{0,16}"
            r"(받아야|해야|필요|시작|권하|할까요|하나요|하면\s*좋|해도\s*(되|돼)|할\s*정도)|"
            r"(받아야|해야|필요|하면\s*좋|해도\s*(되|돼)|할\s*정도).{0,16}(수술|시술|항암|입원)|"
            r"(높|낮|이상|초과|미만|수치|검사|검진|결과|이면|라면|나오).{0,28}"
            r"(복부초음파|초음파|CT|ct|MRI|mri|내시경|조직검사|조영술)\s*\??\s*$|"
            r"(복부초음파|초음파|CT|ct|MRI|mri|내시경|조직검사|조영술).{0,16}"
            r"(받아야|해야|필요|찍어야|찍는\s*게\s*좋|할까요|하나요|하면\s*좋|해도\s*(되|돼))|"
            r"(정밀\s*검사|추가\s*검사|조직검사|추적\s*검사).{0,16}"
            r"(받아야|해야|필요|할까요|하나요|하면\s*좋)|"
            r"(받아야|해야|필요|찍어야|찍는\s*게\s*좋|하면\s*좋|해도\s*(되|돼)).{0,16}"
            r"(복부초음파|초음파|CT|ct|MRI|mri|내시경|조직검사|조영술|정밀\s*검사|추가\s*검사)|"
            r"주사\s*(맞|놓).{0,12}(해야|되나|될까요|돼|되|필요|좋나|괜찮)"
        ),
    ),
    (
        QuestionType.CHECKUP_SUMMARY,
        "summary_rule",
        re.compile(r"검진\s*결과.*(확인해야|신경\s*쓸|요약|전체|전반|제일\s*(문제|신경))"),
    ),
    (
        QuestionType.APP_HELP,
        "app_help_rule",
        re.compile(
            r"업로드|로그인|회원가입|사용법|"
            r"PDF.*(어디|업로드|올리|등록|첨부|제출)|"
            r"(결과|기록).*(어디|메뉴|화면|보는\s*법|확인\s*(방법|위치)|어떻게\s*(봐|확인))"
        ),
    ),
    (
        QuestionType.OUT_OF_SCOPE_NONMEDICAL,
        "out_of_scope_rule",
        re.compile(r"배고파|날씨|주식|로또|영화\s*추천|맛집|여행|환율|코딩"),
    ),
]

_SYMPTOM_HINT = re.compile(
    r"아파|통증|쑤셔|어지러|메스꺼|토할|열이\s*나|기침|설사|배가\s*아|"
    r"탈수|우울|불안|저리|저린|저려|피곤|황달|목마르|목말라|갈증|소변.{0,8}피|혈뇨|"
    r"(허리|목|어깨|무릎|배|복부|갑상선|전립선)\s*(가|이|도)?\s*"
    r"(아프|아픈|아파|통증|쑤셔|저리|저린|저려|불편|붓|부었|부어|멍울|혹|만져|찌릿|뻐근)"
)

_TOKEN = re.compile(r"[A-Za-z0-9가-힣γ]+")
_COMPACT_REMOVE = re.compile(r"[\s\-_/.()]+")
_CHECKUP_INTENT = re.compile(
    r"수치|검사|검진|결과|정상|범위|높|낮|의미|뜻|뭐|어때|봐줘|확인|설명|비교|"
    r"관리|음식|식사|운동|생활습관|줄이면|낮추|좋은|조심|상담|진료과|어느\s*과|어떤\s*과"
)
_LIFESTYLE_INTENT = re.compile(r"관리|음식|식사|운동|생활습관|줄이면|낮추|좋은|조심|술|체중")
_DEPARTMENT_INTENT = re.compile(r"진료과|어느\s*과|어떤\s*과|무슨\s*과|상담")
_SHORTHAND_DIAGNOSIS_DISEASES = (
    "당뇨", "당뇨병", "고혈압", "고지혈증", "암", "종양",
    "간암", "위암", "대장암", "갑상선암", "간경화", "신부전", "빈혈", "통풍",
    "갑상선기능저하증", "갑상선기능항진증", "지방간", "간염", "담석", "요로결석",
)
_DISEASE_LIKE_SUFFIX = r"[가-힣A-Za-z0-9]{2,}(?:증|염|암|병|경화|혈증|부전|결석|장애)"
_SHORTHAND_DIAGNOSIS_TARGET = (
    rf"(?:{'|'.join(_SHORTHAND_DIAGNOSIS_DISEASES)}|{_DISEASE_LIKE_SUFFIX})"
)
_SHORTHAND_DIAGNOSIS = re.compile(
    r"(높|낮|이상|초과|미만|수치|검사|검진|결과|이면|라면|나오).{0,28}"
    rf"{_SHORTHAND_DIAGNOSIS_TARGET}\s*(?:이야|야|인가요|인가|일까|일까요|인지|맞나요)?\s*\??$"
)
_DIAGNOSIS_CONTEXT = re.compile(
    rf"{_SHORTHAND_DIAGNOSIS_TARGET}.{{0,12}}"
    r"(의심|소견|가능성|일\s*수|으로\s*봐야|걸린|걸렸|맞아|맞나요|진단|확정)|"
    r"(의심|소견|가능성|진단|확정).{0,16}"
    rf"{_SHORTHAND_DIAGNOSIS_TARGET}"
)
_DISEASE_ENCYCLOPEDIA = re.compile(
    rf"^\s*{_SHORTHAND_DIAGNOSIS_TARGET}\s*(이|가|은|는)?\s*(뭐야|뭔가요|무엇인가요)\s*\??\s*$"
)
_DISEASE_EXPLAIN_REQUEST = re.compile(
    rf"^\s*(?:{'|'.join(_SHORTHAND_DIAGNOSIS_DISEASES)})\s*(이|가|은|는|의)?\s*"
    r"(무슨\s*)?(뜻|의미|설명|알려).*$"
)
_CHECKUP_SHORT_ALIASES = (
    "감마", "당화", "총콜", "중성", "크레아", "사구체", "허리", "복부", "갑상선", "전립선",
)
_CHECKUP_CATEGORY_TERMS = (
    "콜레스테롤", "혈당", "혈압", "간수치", "간기능", "빈혈", "신장", "콩팥",
    "통풍", "비만", "체중", "전해질", "공복혈당장애",
)
_CATEGORY_ALLOW_CONTEXT = re.compile(
    r"수치|검사|검진|결과|정상|범위|높|낮|의미|뜻|설명|확인|봐줘|비교|관리|음식|식사|운동|"
    r"생활습관|줄이면|낮추|좋은|조심|술|체중|진료과|어느\s*과|어떤\s*과|무슨\s*과|상담"
)
_JOSA_SUFFIXES = (
    "에서는", "에서", "으로", "하고", "에게", "까지", "부터", "처럼", "보다",
    "은", "는", "이", "가", "을", "를", "도", "만", "랑", "와", "과", "의", "에", "로",
)


def _compact_key(text: str) -> str:
    return _COMPACT_REMOVE.sub("", text).strip().lower()


_CHECKUP_SHORT_ALIAS_KEYS = {_compact_key(alias) for alias in _CHECKUP_SHORT_ALIASES}
_CHECKUP_CATEGORY_KEYS = {_compact_key(term) for term in _CHECKUP_CATEGORY_TERMS}


def _strip_josa(text: str) -> str:
    for suffix in _JOSA_SUFFIXES:
        if text.endswith(suffix) and len(text) > len(suffix):
            return text[: -len(suffix)]
    return text


def _build_checkup_terms() -> set[str]:
    terms = set(reference_dict.REFERENCE)
    terms.update(SYNONYMS)
    terms.update(_CHECKUP_SHORT_ALIASES)
    compact_terms = {_compact_key(term) for term in terms}
    return {term for term in compact_terms if len(term) >= 2}


_CHECKUP_TERMS = _build_checkup_terms()


def _question_windows(question: str, max_tokens: int = 3) -> list[str]:
    tokens = list(_TOKEN.finditer(question))
    windows: list[str] = []
    for i, start_token in enumerate(tokens):
        for size in range(1, max_tokens + 1):
            end_idx = i + size - 1
            if end_idx >= len(tokens):
                break
            end_token = tokens[end_idx]
            windows.append(_compact_key(question[start_token.start(): end_token.end()]))
    return windows


def _normalized_windows(question: str) -> list[str]:
    normalized: list[str] = []
    for key in _question_windows(question):
        for candidate in (key, _strip_josa(key)):
            if candidate and candidate not in normalized:
                normalized.append(candidate)
    return normalized


def _has_checkup_item_hint(question: str) -> bool:
    windows = _normalized_windows(question)
    if any(key in _CHECKUP_TERMS for key in windows):
        return True
    if any(key in _CHECKUP_SHORT_ALIAS_KEYS for key in windows):
        return True

    fuzzy_hits: set[str] = set()
    for key in windows:
        if len(key) < 4:
            continue
        for term in _CHECKUP_TERMS:
            if len(term) < 4:
                continue
            if fuzz.ratio(key, term) >= 80:
                fuzzy_hits.add(term)
                if len(fuzzy_hits) > 1:
                    return False
    return len(fuzzy_hits) == 1


def _has_checkup_category_hint(question: str) -> bool:
    windows = _normalized_windows(question)
    return any(key in _CHECKUP_CATEGORY_KEYS for key in windows)


def _shorthand_diagnosis_decision(question: str) -> ScopeDecision | None:
    if not _SHORTHAND_DIAGNOSIS.search(question):
        return None
    return ScopeDecision(
        scope=Scope.BLOCKED,
        routed=True,
        reason="rule",
        question_type=QuestionType.DIAGNOSIS_REQUEST,
        route_reason="diagnosis_rule",
    )


def _diagnosis_context_decision(question: str) -> ScopeDecision | None:
    if not _DIAGNOSIS_CONTEXT.search(question):
        return None
    return ScopeDecision(
        scope=Scope.BLOCKED,
        routed=True,
        reason="rule",
        question_type=QuestionType.DIAGNOSIS_REQUEST,
        route_reason="diagnosis_rule",
    )


def _allowed_checkup_decision(question: str) -> ScopeDecision | None:
    """실제 말투의 명확한 검진 항목 질문은 LLM 분류기 전 단계에서 허용한다."""
    if not _CHECKUP_INTENT.search(question):
        return None
    has_item_hint = _has_checkup_item_hint(question)
    has_category_hint = _has_checkup_category_hint(question)
    if not has_item_hint and not has_category_hint:
        return None
    if has_category_hint and not has_item_hint and not _CATEGORY_ALLOW_CONTEXT.search(question):
        return None

    question_type = QuestionType.CHECKUP_EXPLANATION
    if _DEPARTMENT_INTENT.search(question):
        question_type = QuestionType.DEPARTMENT_GUIDE
    elif _LIFESTYLE_INTENT.search(question):
        question_type = QuestionType.LIFESTYLE_GENERAL

    return ScopeDecision(
        scope=Scope.ALLOWED,
        routed=False,
        reason="rule",
        question_type=question_type,
        route_reason="checkup_item_rule",
    )

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
        "현재 챗봇은 최신 검진 결과 1건을 기준으로 수치 의미, 생활습관 관리, 진료과 상담 방향을 안내합니다. "
        "과거 결과와의 추세 비교, 실제 병원 추천, 비용·보험·실비 정보는 아직 지원하지 않습니다."
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

    deferred_allow: ScopeDecision | None = None
    for question_type, route_reason, pattern in _RULE_PATTERNS:
        if pattern.search(text):
            decision = ScopeDecision(
                scope=scope_for_question_type(question_type),
                routed=scope_for_question_type(question_type) == Scope.BLOCKED,
                reason="rule",
                question_type=question_type,
                route_reason=route_reason,
            )
            if decision.scope == Scope.ALLOWED:
                deferred_allow = decision
                continue
            return decision

    if _SYMPTOM_HINT.search(text):
        return ScopeDecision(
            scope=Scope.BLOCKED,
            routed=True,
            reason="rule",
            question_type=QuestionType.SYMPTOM_NON_EMERGENCY,
            route_reason="symptom_rule",
        )

    diagnosis_decision = _shorthand_diagnosis_decision(text)
    if diagnosis_decision is not None:
        return diagnosis_decision

    diagnosis_context_decision = _diagnosis_context_decision(text)
    if diagnosis_context_decision is not None:
        return diagnosis_context_decision

    if _DISEASE_ENCYCLOPEDIA.search(text) or _DISEASE_EXPLAIN_REQUEST.search(text):
        return ScopeDecision(
            scope=Scope.BLOCKED,
            routed=True,
            reason="rule",
            question_type=QuestionType.UNSUPPORTED,
            route_reason="unsupported_rule",
        )

    if deferred_allow is not None:
        return deferred_allow

    return _allowed_checkup_decision(text)


def classify_rule(question: str) -> Scope | None:
    """규칙 기반 하드 차단 - 명백한 비허용이면 BLOCKED, 아니면 None(LLM 위임)"""
    decision = classify_rule_detail(question)
    return decision.scope if decision is not None else None
