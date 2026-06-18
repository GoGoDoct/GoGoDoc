"""F-007 챗봇 스코프 규칙 단위 테스트 - 하드 차단 패턴 (순수 도메인)"""

from gogodoc.domain import chat_scope
from gogodoc.domain.models import QuestionType, Scope


def test_blocks_prescription_and_medication():
    # 처방·복약 질문 하드 차단
    for q in ["무슨 약을 먹어야 하나요?", "혈압약 복용해도 되나요?", "메트포민 용량 얼마예요?",
              "콜레스테롤 약 처방해줘", "지금 먹는 약 끊어도 되나요?"]:
        assert chat_scope.classify_rule(q) == Scope.BLOCKED, q


def test_blocks_diagnosis_and_procedure():
    # 진단 단정·의료행위 하드 차단
    for q in ["저 당뇨병인가요?", "이거 암이에요?", "제 병명이 뭔가요?",
              "수술을 받아야 하나요?", "항암치료 시작해야 하나요?"]:
        assert chat_scope.classify_rule(q) == Scope.BLOCKED, q


def test_allowed_questions_not_hard_blocked():
    # 허용 질문은 규칙에서 차단하면 안 됨. 명확한 검진 항목 질문은 rule 허용될 수 있다.
    for q in ["ALT가 60인데 무슨 의미예요?", "콜레스테롤 낮추려면 어떤 음식이 좋아요?",
              "혈압 관리에 좋은 운동 알려줘", "어느 진료과를 가야 하나요?"]:
        assert chat_scope.classify_rule(q) in (None, Scope.ALLOWED), q


def test_reference_range_comparison_not_hard_blocked():
    # 정상범위와의 비교는 최신 검진 결과 설명 범위라 LLM/RAG 경로로 위임
    assert chat_scope.classify_rule("LDL 수치를 정상범위와 비교해줘") in (None, Scope.ALLOWED)


def test_lab_unit_mgdl_question_not_dosage_routed():
    # mg/dL은 검사 단위이므로 약물 용량 질문으로 과차단하면 안 됨
    assert chat_scope.classify_rule("LDL은 몇 mg/dL부터 높은 거예요?") in (None, Scope.ALLOWED)


def test_medication_context_mg_still_dosage_routed():
    # 약물 문맥의 mg 질문은 용량 판단으로 하드 차단
    d = chat_scope.classify_rule_detail("메트포민 몇 mg 먹어야 돼요?")
    assert d is not None
    assert d.scope == Scope.BLOCKED
    assert d.question_type == QuestionType.DOSAGE_REQUEST


def test_past_result_comparison_still_unsupported():
    # 과거 결과와의 추세 비교는 최신 검진 1건 기준 범위를 벗어나므로 미지원 라우팅
    d = chat_scope.classify_rule_detail("작년보다 혈당이 오른 건가요?")
    assert d is not None
    assert d.scope == Scope.BLOCKED
    assert d.question_type == QuestionType.UNSUPPORTED


def test_waist_circumference_not_symptom_routed():
    # 허리둘레는 지원되는 검진 항목이므로 단독 '허리' 증상 힌트로 차단하면 안 됨
    assert chat_scope.classify_rule("허리둘레가 95cm인데 무슨 의미예요?") in (None, Scope.ALLOWED)


def test_rule_routes_emergency_symptoms_before_llm():
    # 응급 가능 증상은 답변 생성 전에 즉시 라우팅
    for q in [
        "가슴이 답답하고 숨이 차요",
        "한쪽 팔에 힘이 안 들어가고 말이 어눌해요",
        "갑자기 의식을 잃었어요",
        "숨쉬기 힘들어요",
        "숨 못 쉬겠어요",
    ]:
        d = chat_scope.classify_rule_detail(q)
        assert d is not None
        assert d.scope == Scope.BLOCKED
        assert d.question_type == QuestionType.EMERGENCY_SYMPTOM


def test_rule_routes_colloquial_diagnosis_and_med_recommendation_before_llm():
    # 구어체 진단·약 추천도 LLM 변동성에 맡기지 않고 rule 단계에서 차단
    diagnosis = chat_scope.classify_rule_detail("나 당뇨야?")
    prescription = chat_scope.classify_rule_detail("고지혈증 약 추천해줘")

    assert diagnosis is not None
    assert diagnosis.scope == Scope.BLOCKED
    assert diagnosis.question_type == QuestionType.DIAGNOSIS_REQUEST
    assert prescription is not None
    assert prescription.scope == Scope.BLOCKED
    assert prescription.question_type == QuestionType.PRESCRIPTION_REQUEST


def test_rule_routes_self_harm_crisis_before_llm():
    # 자해·자살 위기 표현은 별도 위기 안내로 라우팅
    d = chat_scope.classify_rule_detail("죽고 싶어요")
    assert d is not None
    assert d.scope == Scope.BLOCKED
    assert d.question_type == QuestionType.SELF_HARM_CRISIS


def test_rule_routes_general_symptom_and_nonmedical_out_of_scope():
    # 일반 증상과 비의료 질문은 서로 다른 유형으로 라우팅
    symptom = chat_scope.classify_rule_detail("나 지금 허리가 아픈데")
    out_of_scope = chat_scope.classify_rule_detail("나 지금 배고파")

    assert symptom is not None
    assert symptom.scope == Scope.BLOCKED
    assert symptom.question_type == QuestionType.SYMPTOM_NON_EMERGENCY
    assert out_of_scope is not None
    assert out_of_scope.scope == Scope.BLOCKED
    assert out_of_scope.question_type == QuestionType.OUT_OF_SCOPE_NONMEDICAL


def test_general_symptom_is_not_captured_by_summary_wording():
    # 제일 신경 같은 표현이 있어도 증상 원인 질문이면 결과 요약으로 허용하지 않음
    d = chat_scope.classify_rule_detail("제일 신경 쓰이는 건 허리가 아픈 건데 왜 이래요?")

    assert d is not None
    assert d.scope == Scope.BLOCKED
    assert d.question_type == QuestionType.SYMPTOM_NON_EMERGENCY


def test_empty_question_blocked():
    # 빈 질문은 보수적으로 차단
    assert chat_scope.classify_rule("") == Scope.BLOCKED
    assert chat_scope.classify_rule("   ") == Scope.BLOCKED
    assert chat_scope.classify_rule_detail("").question_type == QuestionType.UNKNOWN


def test_pdf_or_result_words_do_not_hide_checkup_question():
    # PDF 표현이 있어도 검진 항목 해석 의도면 앱 도움말로 과차단하지 않음
    assert chat_scope.classify_rule("PDF에 나온 ALT 수치가 뭐예요?") in (None, Scope.ALLOWED)


def test_rule_routes_obvious_checkup_summary_question():
    # 최신 결과에서 확인해야 할 항목을 묻는 질문은 앱 도움말이 아니라 결과 요약으로 고정
    for question in (
        "검진 결과 확인해야 할 항목 알려줘",
        "검진 결과 요약",
    ):
        d = chat_scope.classify_rule_detail(question)
        assert d is not None, question
        assert d.scope == Scope.ALLOWED, question
        assert d.question_type == QuestionType.CHECKUP_SUMMARY, question


def test_rule_routes_medication_and_dosage_edge_cases():
    # 실제 사용자 질문형 약물 판단은 처방·복약 또는 용량 판단으로 차단
    cases = [
        ("LDL이 높은데 스타틴 먹어야 하나요?", QuestionType.PRESCRIPTION_REQUEST),
        ("메트포민을 몇 mg으로 늘려야 하나요?", QuestionType.DOSAGE_REQUEST),
        ("스타틴 부작용이 걱정돼요. 계속 먹어도 되나요?", QuestionType.PRESCRIPTION_REQUEST),
        ("혈압 높으면 약?", QuestionType.PRESCRIPTION_REQUEST),
    ]

    for question, expected in cases:
        d = chat_scope.classify_rule_detail(question)
        assert d is not None, question
        assert d.scope == Scope.BLOCKED
        assert d.question_type == expected


def test_rule_routes_pediatric_red_flags_and_general_symptoms():
    # 소아 red flag는 응급, 일반 탈수 걱정은 일반 증상으로 라우팅
    emergency = chat_scope.classify_rule_detail("아이가 축 처지고 소변이 거의 없어요")
    symptom = chat_scope.classify_rule_detail("소아 탈수 증상이 걱정돼요")

    assert emergency is not None
    assert emergency.scope == Scope.BLOCKED
    assert emergency.question_type == QuestionType.EMERGENCY_SYMPTOM
    assert symptom is not None
    assert symptom.scope == Scope.BLOCKED
    assert symptom.question_type == QuestionType.SYMPTOM_NON_EMERGENCY


def test_rule_routes_pregnancy_and_mental_health_boundaries():
    # 임신 가능성·우울감 상담은 검진 챗봇 범위를 벗어난 안전 라우팅
    pregnancy = chat_scope.classify_rule_detail("이 검진 결과로 임신 가능성이 있나요?")
    pregnancy_range = chat_scope.classify_rule_detail("임신 중이라면 이 검사 수치 기준이 달라지나요?")
    mental = chat_scope.classify_rule_detail("요즘 너무 우울한데 어떻게 해야 하나요?")

    assert pregnancy is not None
    assert pregnancy.scope == Scope.BLOCKED
    assert pregnancy.question_type == QuestionType.DIAGNOSIS_REQUEST
    assert pregnancy_range is not None
    assert pregnancy_range.scope == Scope.BLOCKED
    assert pregnancy_range.question_type == QuestionType.UNSUPPORTED
    assert mental is not None
    assert mental.scope == Scope.BLOCKED
    assert mental.question_type == QuestionType.SYMPTOM_NON_EMERGENCY


def test_rule_routes_cost_as_unsupported_before_procedure():
    # 비용·보험 질문은 시술 필요 여부가 아니라 현재 미지원 정보로 분리
    cost = chat_scope.classify_rule_detail("위내시경 용종 제거 비용이 얼마예요?")
    procedure = chat_scope.classify_rule_detail("이 수치면 시술을 받아야 하나요?")

    assert cost is not None
    assert cost.scope == Scope.BLOCKED
    assert cost.question_type == QuestionType.UNSUPPORTED
    assert procedure is not None
    assert procedure.scope == Scope.BLOCKED
    assert procedure.question_type == QuestionType.PROCEDURE_REQUEST


def test_rule_routes_common_procedure_judgment_phrases():
    cases = [
        "수술하면 좋나요?",
        "입원할 정도인가요?",
        "주사 맞아도 돼요?",
    ]

    for question in cases:
        d = chat_scope.classify_rule_detail(question)
        assert d is not None, question
        assert d.scope == Scope.BLOCKED
        assert d.question_type == QuestionType.PROCEDURE_REQUEST


def test_rule_blocks_summary_wording_when_symptom_context_present():
    # 결과 요약처럼 보여도 실제로 증상 원인을 묻는 질문이면 증상 라우팅이 우선한다.
    d = chat_scope.classify_rule_detail("검진 결과에서 제일 신경 쓸 건 피곤함인데 왜죠?")

    assert d is not None
    assert d.scope == Scope.BLOCKED
    assert d.question_type == QuestionType.SYMPTOM_NON_EMERGENCY


def test_unsupported_routing_message_mentions_cost_and_trend_limits():
    message = chat_scope.routing_message(QuestionType.UNSUPPORTED)

    assert "추세 비교" in message
    assert "비용" in message
    assert "보험" in message


def test_rule_keeps_lifestyle_stress_question_allowed_for_llm():
    # 스트레스 관리가 검진 생활습관 질문이면 증상 차단하지 않음
    d = chat_scope.classify_rule_detail("스트레스 줄이면 혈압 관리에 도움이 되나요?")

    assert d is None or d.scope == Scope.ALLOWED


def test_rule_allows_common_real_phrasing_checkup_item_questions_before_llm():
    # 실제 말투의 짧은 항목 질문은 LLM 분류기 변동성에 맡기지 않고 rule 단계에서 허용
    cases = [
        "AST 수치도 같이 봐줘",
        "내 감마 지티피 어때",
        "내 감마지피티 어때",
        "triglycerides 수치 봐줘",
        "헤모글로빈 수치 봐줘",
        "내 허리 어때",
        "내 복부 어때",
        "갑상선 수치 봐줘",
        "전립선 수치 어때",
    ]

    for question in cases:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.ALLOWED, question
        assert d.routed is False, question
        assert d.question_type == QuestionType.CHECKUP_EXPLANATION, question
        assert d.route_reason == "checkup_item_rule", question


def test_rule_does_not_allow_alias_when_question_is_symptom_or_nonmedical():
    # 같은 짧은 단어라도 증상이나 비의료 문맥이면 기존 차단 규칙이 우선한다.
    symptom = chat_scope.classify_rule_detail("나 지금 허리가 아픈데")
    nonmedical = chat_scope.classify_rule_detail("지피티가 뭐야")
    chatgpt = chat_scope.classify_rule_detail("ChatGPT 뭐야?")

    assert symptom is not None
    assert symptom.scope == Scope.BLOCKED
    assert symptom.question_type == QuestionType.SYMPTOM_NON_EMERGENCY
    assert nonmedical is None
    assert chatgpt is None


def test_rule_blocks_shorthand_diagnosis_questions_before_checkup_allow():
    # 항목명과 해석 의도가 있어도 질병명 단정 질문이면 진단 요청으로 차단한다.
    cases = [
        "공복혈당 높으면 당뇨?",
        "PSA 높으면 암?",
        "콜레스테롤 높으면 고지혈증?",
        "혈압 높으면 고혈압?",
        "간수치 높으면 간경화?",
        "TSH 높으면 갑상선기능저하증?",
        "ALT 높으면 지방간?",
        "ALT 높으면 지방간일까?",
        "간수치 높으면 간염인가요?",
        "TSH 높으면 갑상선기능저하증일까요?",
    ]

    for question in cases:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.BLOCKED, question
        assert d.routed is True, question
        assert d.question_type == QuestionType.DIAGNOSIS_REQUEST, question


def test_rule_blocks_diagnosis_suspicion_phrases_before_checkup_allow():
    # 질병명 뒤에 의심·소견·가능성이 붙은 질문도 검진 설명이 아니라 진단 요청이다.
    cases = [
        "공복혈당 높으면 당뇨 의심인가요?",
        "PSA 수치 높으면 전립선암 의심돼요?",
        "간수치 높으면 간경화일 수 있나요?",
        "콜레스테롤 높으면 고지혈증으로 봐야 하나요?",
        "CEA 높으면 암 소견인가요?",
    ]

    for question in cases:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.BLOCKED, question
        assert d.routed is True, question
        assert d.question_type == QuestionType.DIAGNOSIS_REQUEST, question


def test_rule_keeps_non_diagnosis_management_question_allowed():
    # 같은 항목 표현이라도 관리 질문이면 진단 차단이 아니라 허용 질문으로 유지한다.
    d = chat_scope.classify_rule_detail("공복혈당이 높으면 어떻게 관리해?")

    assert d is not None
    assert d.scope == Scope.ALLOWED
    assert d.question_type == QuestionType.LIFESTYLE_GENERAL


def test_rule_blocks_medication_questions_before_checkup_allow():
    # 항목명과 낮추기 의도가 있어도 약물·주사 질문이면 답변 생성 전에 차단한다.
    cases = [
        "LDL 낮추는 약 뭐야",
        "혈당 낮추는 주사 뭐야",
        "혈압 높으면 약 필요해?",
        "혈압 높으면 혈압약 필요해?",
        "공복혈당 높으면 당뇨약?",
        "혈압 높으면 혈압약?",
        "LDL 높으면 고지혈증약?",
        "혈압 높으면 약?",
    ]

    for question in cases:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.BLOCKED, question
        assert d.routed is True, question
        assert d.question_type == QuestionType.PRESCRIPTION_REQUEST, question


def test_rule_blocks_treatment_need_phrases_before_checkup_allow():
    # 약 필요·써야·먹어야 같은 치료 필요 여부 판단도 RAG로 내려가지 않는다.
    cases = [
        "혈당 높으면 약 써야 하나요?",
        "LDL 높으면 약 필요할까요?",
        "빈혈 수치 낮으면 철분제 먹어야 하나요?",
        "혈당 높으면 인슐린 맞아야 하나요?",
    ]

    for question in cases:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.BLOCKED, question
        assert d.routed is True, question
        assert d.question_type == QuestionType.PRESCRIPTION_REQUEST, question


def test_rule_blocks_body_part_symptom_before_short_alias_allow():
    # 허리·복부가 항목 alias여도 저림 같은 증상 문맥이면 허리둘레 해석으로 허용하지 않는다.
    cases = [
        "내 허리가 저린데 어때",
        "복부가 불편한데 어때",
        "갑상선이 부었는데 어때",
    ]

    for question in cases:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.BLOCKED, question
        assert d.routed is True, question
        assert d.question_type == QuestionType.SYMPTOM_NON_EMERGENCY, question


def test_rule_blocks_diagnostic_test_decisions_before_checkup_allow():
    # 검사·시술 필요 여부 판단은 검진 수치 설명이 아니라 의료진 상담 라우팅 대상이다.
    cases = [
        "ALT 높으면 복부초음파 해야 해?",
        "CEA 높으면 내시경 받아야 해?",
        "LDL 높으면 CT 찍어야 해?",
        "간수치 높으면 MRI 받아야 해?",
        "간수치 높으면 정밀검사 받아야 하나요?",
        "LDL 높으면 CT 찍는 게 좋나요?",
        "간수치 높으면 추가 검사 필요할까요?",
        "ALT 높으면 복부초음파?",
        "간수치 높으면 초음파?",
        "CEA 높으면 내시경?",
    ]

    for question in cases:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.BLOCKED, question
        assert d.routed is True, question
        assert d.question_type == QuestionType.PROCEDURE_REQUEST, question


def test_rule_blocks_uncovered_symptom_phrases_before_checkup_allow():
    # 항목명·카테고리가 있어도 증상 호소가 섞이면 수치 설명으로 허용하지 않는다.
    cases = [
        "혈압 높은데 가슴이 뻐근해요 뭐죠?",
        "혈당 높은데 자꾸 목말라요 뭐예요?",
        "간수치 높고 황달이 있어요 뭐죠?",
        "신장 수치 낮고 소변에 피가 보여요 뭐죠?",
    ]

    for question in cases:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.BLOCKED, question
        assert d.routed is True, question
        assert d.question_type in (
            QuestionType.SYMPTOM_NON_EMERGENCY,
            QuestionType.EMERGENCY_SYMPTOM,
        ), question


def test_rule_does_not_allow_disease_encyclopedia_prompts_as_checkups():
    # 질병명 단독 백과사전 질문은 최신 검진 결과 해석이 아니므로 rule allowlist에서 바로 허용하지 않는다.
    for question in [
        "빈혈이 뭐야",
        "통풍이 뭐야",
        "공복혈당장애가 뭐야",
        "빈혈 설명해줘",
        "통풍 뜻 알려줘",
        "갑상선기능저하증 설명해줘",
    ]:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.BLOCKED, question
        assert d.question_type == QuestionType.UNSUPPORTED, question


def test_rule_keeps_category_management_questions_allowed():
    # 카테고리 단어만 있어도 관리·수치·검진 문맥이면 최신 결과 해석 범위로 허용한다.
    cases = [
        ("혈압 관리에 좋은 운동 알려줘", QuestionType.LIFESTYLE_GENERAL),
        ("콜레스테롤 수치 봐줘", QuestionType.CHECKUP_EXPLANATION),
        ("공복혈당장애가 무슨 뜻인지 쉽게 설명해줘", QuestionType.CHECKUP_EXPLANATION),
        ("LDL이 약간 높으면 관리 필요해?", QuestionType.LIFESTYLE_GENERAL),
        ("혈당이 약간 높으면 운동해야 하나요?", QuestionType.LIFESTYLE_GENERAL),
    ]

    for question, expected_type in cases:
        d = chat_scope.classify_rule_detail(question)

        assert d is not None, question
        assert d.scope == Scope.ALLOWED, question
        assert d.question_type == expected_type, question
