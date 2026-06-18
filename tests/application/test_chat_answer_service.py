"""F-007 ChatAnswerService 테스트 - 안전 게이트 + RAG 답변 통합 래퍼."""

from gogodoc.application.chat_answer_service import ChatAnswerService
from gogodoc.application.chat_rag_service import ChatRagService
from gogodoc.application.chat_service import ChatService
from gogodoc.application.ports import LLMTask
from gogodoc.domain.models import QuestionType, Scope
from gogodoc.domain.policy import DISCLAIMER


class _CountingLLM:
    """호출 내용을 기록하는 가짜 LLM."""

    def __init__(self, response: str):
        self.response = response
        self.calls: list[dict] = []

    def complete(self, system: str, user: str, task: LLMTask) -> str:
        self.calls.append({"system": system, "user": user, "task": task})
        return self.response


def _latest_analysis() -> dict:
    return {
        "tracking_items": ["ALT", "BMI"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "ALT",
                "value": 60,
                "value_text": "60",
                "unit": "U/L",
                "status": "주의",
                "explain": "간 건강을 보는 대표 지표입니다.",
                "source": "질병관리청 국가건강정보포털 간기능검사",
            },
            {
                "name": "BMI",
                "value": 27.1,
                "value_text": "27.1",
                "unit": "kg/m2",
                "status": "이상",
                "explain": "키 대비 체중으로 비만 정도를 보는 체질량지수입니다.",
                "source": "대한비만학회 비만 진료지침",
            },
        ],
    }


def _empty_latest_analysis() -> dict:
    return {
        "tracking_items": [],
        "emergency_alerts": [],
        "items_json": [],
    }


def _rich_latest_analysis() -> dict:
    return {
        "tracking_items": ["수축기혈압", "이완기혈압", "당화혈색소"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "수축기혈압",
                "value": 138,
                "value_text": "138",
                "unit": "mmHg",
                "status": "주의",
                "explain": "혈압 상태를 보는 수축기 지표입니다.",
                "source": "대한고혈압학회 고혈압 진료지침",
            },
            {
                "name": "이완기혈압",
                "value": 86,
                "value_text": "86",
                "unit": "mmHg",
                "status": "주의",
                "explain": "혈압 상태를 보는 이완기 지표입니다.",
                "source": "대한고혈압학회 고혈압 진료지침",
            },
            {
                "name": "당화혈색소",
                "value": 5.8,
                "value_text": "5.8",
                "unit": "%",
                "status": "주의",
                "explain": "최근 혈당 흐름을 보는 지표입니다.",
                "source": "대한당뇨병학회 당뇨병 진료지침",
            },
            {
                "name": "공복혈당",
                "value": 92,
                "value_text": "92",
                "unit": "mg/dL",
                "status": "정상",
                "explain": "공복 상태의 혈당을 보는 지표입니다.",
                "source": "대한당뇨병학회 당뇨병 진료지침",
            },
            {
                "name": "총콜레스테롤",
                "value": 225,
                "value_text": "225",
                "unit": "mg/dL",
                "status": "주의",
                "explain": "혈중 전체 콜레스테롤 양을 보는 지표입니다.",
                "source": "서울대학교병원 의학정보 이상지질혈증",
            },
            {
                "name": "LDL 콜레스테롤",
                "value": 145,
                "value_text": "145",
                "unit": "mg/dL",
                "status": "주의",
                "explain": "혈관에 쌓이기 쉬운 콜레스테롤입니다.",
                "source": "서울대학교병원 의학정보 이상지질혈증",
            },
            {
                "name": "HDL 콜레스테롤",
                "value": 42,
                "value_text": "42",
                "unit": "mg/dL",
                "status": "정상",
                "explain": "혈관 건강에 도움이 되는 콜레스테롤입니다.",
                "source": "서울대학교병원 의학정보 이상지질혈증",
            },
            {
                "name": "중성지방",
                "value": 180,
                "value_text": "180",
                "unit": "mg/dL",
                "status": "주의",
                "explain": "혈액 속 지방 성분입니다.",
                "source": "서울대학교병원 의학정보 이상지질혈증",
            },
            {
                "name": "헤모글로빈",
                "value": 13.8,
                "value_text": "13.8",
                "unit": "g/dL",
                "status": "정상",
                "explain": "빈혈 여부를 보는 혈액 지표입니다.",
                "source": "서울아산병원 의료정보 일반혈액검사",
            },
        ],
    }


def _gamma_latest_analysis() -> dict:
    return {
        "tracking_items": ["감마지티피"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "감마지티피",
                "value": 68,
                "value_text": "68",
                "unit": "U/L",
                "status": "주의",
                "explain": "간담도계 상태를 함께 보는 효소 지표입니다.",
                "source": "연세대 의과대학 건강정보 감마글루타밀전이효소",
            },
            {
                "name": "ALT",
                "value": 28,
                "value_text": "28",
                "unit": "U/L",
                "status": "정상",
                "explain": "간 건강을 보는 대표 지표입니다.",
                "source": "질병관리청 국가건강정보포털 간기능검사",
            },
        ],
    }


def test_blocked_question_returns_routing_without_rag_llm_call():
    classifier_llm = _CountingLLM("허용")
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("무슨 약을 먹어야 하나요?", _latest_analysis())

    assert msg.routed is True
    assert msg.scope_flag == Scope.BLOCKED
    assert msg.question_type == QuestionType.PRESCRIPTION_REQUEST
    assert "전문의" in msg.content
    assert DISCLAIMER in msg.content
    assert classifier_llm.calls == []
    assert answer_llm.calls == []


def test_allowed_question_converts_latest_analysis_to_report_for_rag():
    classifier_llm = _CountingLLM('{"scope":"allowed","question_type":"lifestyle_general","route_reason":"생활습관"}')
    answer_llm = _CountingLLM("BMI는 체중과 키의 관계를 보는 지표입니다.")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("BMI가 높으면 어떻게 관리해요?", _latest_analysis())

    assert msg.routed is False
    assert msg.scope_flag == Scope.ALLOWED
    assert msg.question_type == QuestionType.LIFESTYLE_GENERAL
    assert msg.context_item_names == ["BMI"]
    assert any("대한비만학회" in source for source in msg.sources)
    assert DISCLAIMER in msg.content

    assert len(answer_llm.calls) == 1
    call = answer_llm.calls[0]
    assert call["task"] == LLMTask.INTERPRET
    assert "BMI" in call["user"]
    assert "내 수치 27.1 (abnormal)" in call["user"]
    assert "생활 가이드 근거" in call["user"]
    assert "대한비만학회" in call["user"]
    assert "ALT" not in call["user"]


def test_out_of_scope_question_routes_without_rag_llm_call():
    classifier_llm = _CountingLLM("허용")
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("오늘 날씨 어때요?", _latest_analysis())

    assert msg.routed is True
    assert msg.scope_flag == Scope.BLOCKED
    assert msg.question_type == QuestionType.OUT_OF_SCOPE_NONMEDICAL
    assert msg.context_item_names == []
    assert msg.sources == []
    assert "건강검진 결과 해석" in msg.content
    assert DISCLAIMER in msg.content
    assert classifier_llm.calls == []
    assert answer_llm.calls == []


def test_missing_latest_result_returns_guidance_without_rag_llm_call():
    classifier_llm = _CountingLLM("허용")
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("ALT가 무슨 뜻이에요?", None)

    assert msg.routed is True
    assert msg.scope_flag == Scope.ALLOWED
    assert msg.question_type == QuestionType.CHECKUP_EXPLANATION
    assert "최신 검진 결과" in msg.content
    assert DISCLAIMER in msg.content
    assert answer_llm.calls == []


def test_emergency_question_returns_119_guidance_without_rag_llm_call():
    classifier_llm = _CountingLLM("허용")
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("가슴이 답답하고 숨이 차요", _latest_analysis())

    assert msg.routed is True
    assert msg.scope_flag == Scope.BLOCKED
    assert msg.question_type == QuestionType.EMERGENCY_SYMPTOM
    assert "119" in msg.content
    assert "진단" in msg.content or "의료" in msg.content
    assert "참고 소견" not in msg.content
    assert classifier_llm.calls == []
    assert answer_llm.calls == []


def test_checkup_summary_uses_latest_result_without_answer_llm_call():
    classifier_llm = _CountingLLM('{"scope":"allowed","question_type":"checkup_summary","route_reason":"전체 요약"}')
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("내 검진 결과 전체적으로 설명해줘", _latest_analysis())

    assert msg.routed is False
    assert msg.scope_flag == Scope.ALLOWED
    assert msg.question_type == QuestionType.CHECKUP_SUMMARY
    assert "최신 검진 결과" in msg.content
    assert "BMI" in msg.content
    assert "ALT" in msg.content
    assert DISCLAIMER in msg.content
    assert answer_llm.calls == []


def test_report_fallback_answer_preserves_classifier_question_type():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"department_guide","route_reason":"진료과 안내"}'
    )
    answer_llm = _CountingLLM("최신 결과의 주의 항목 기준으로 진료과 상담 방향을 안내합니다.")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("어느 진료과 가야 해요?", _latest_analysis())

    assert msg.routed is False
    assert msg.scope_flag == Scope.ALLOWED
    assert msg.question_type == QuestionType.DEPARTMENT_GUIDE
    assert msg.route_reason == "report_fallback_answer"
    assert msg.context_item_names == ["BMI", "ALT"]
    assert msg.sources
    assert "특정 검진 항목을 찾지 못해" in msg.content
    assert len(answer_llm.calls) == 1
    assert "최신 검진 결과 관련 수치 있음" in answer_llm.calls[0]["user"]


def test_report_fallback_accepts_short_department_phrase():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"department_guide","route_reason":"진료과 안내"}'
    )
    answer_llm = _CountingLLM("최신 결과의 주의 항목 기준으로 진료과 상담 방향을 안내합니다.")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("어느 과 가야 해요?", _latest_analysis())

    assert msg.routed is False
    assert msg.scope_flag == Scope.ALLOWED
    assert msg.question_type == QuestionType.DEPARTMENT_GUIDE
    assert msg.route_reason == "report_fallback_answer"
    assert msg.context_item_names == ["BMI", "ALT"]
    assert len(answer_llm.calls) == 1


def test_no_grounding_answer_preserves_question_type_when_report_has_no_fallback_items():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"department_guide","route_reason":"진료과 안내"}'
    )
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("어느 진료과 가야 해요?", _empty_latest_analysis())

    assert msg.routed is False
    assert msg.scope_flag == Scope.ALLOWED
    assert msg.question_type == QuestionType.DEPARTMENT_GUIDE
    assert msg.route_reason == "no_grounding"
    assert msg.context_item_names == []
    assert msg.sources == []
    assert answer_llm.calls == []


def test_reference_only_answer_marks_item_missing_from_latest_result():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"lifestyle_general","route_reason":"생활습관"}'
    )
    answer_llm = _CountingLLM("요산은 생활습관 관리가 중요합니다.")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("요산이 높으면 뭘 조심해야 해요?", _latest_analysis())

    assert msg.routed is False
    assert msg.scope_flag == Scope.ALLOWED
    assert msg.question_type == QuestionType.LIFESTYLE_GENERAL
    assert msg.route_reason == "reference_only_answer"
    assert msg.context_item_names == ["요산"]
    assert msg.sources
    assert "최신 검진 결과에서 요산" in msg.content
    assert "일반 정보" in msg.content
    assert len(answer_llm.calls) == 1
    assert "최신 검진 결과에 해당 항목 없음" in answer_llm.calls[0]["user"]


def test_official_item_containing_short_alias_stays_reference_only_when_missing():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("감마지티피 일반 정보")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("감마지티피가 뭐야", _latest_analysis())

    assert msg.route_reason == "reference_only_answer"
    assert msg.context_item_names == ["감마지티피"]
    assert len(answer_llm.calls) == 1


def test_hba1c_question_does_not_pull_hemoglobin_context():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("당화혈색소 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("당화혈색소 5.8이면 뭘 조심해야 해요?", _rich_latest_analysis())

    assert msg.routed is False
    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == ["당화혈색소"]
    assert len(answer_llm.calls) == 1
    assert "당화혈색소" in answer_llm.calls[0]["user"]
    assert "- 헤모글로빈:" not in answer_llm.calls[0]["user"]


def test_spaced_hba1c_synonym_does_not_pull_hemoglobin_context():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("당화혈색소 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("당화 헤모글로빈 수치가 뭐야", _rich_latest_analysis())

    assert msg.routed is False
    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == ["당화혈색소"]
    assert len(answer_llm.calls) == 1
    assert "당화혈색소" in answer_llm.calls[0]["user"]
    assert "- 헤모글로빈:" not in answer_llm.calls[0]["user"]


def test_blood_sugar_lifestyle_question_uses_category_items_instead_of_uncertain_match():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"lifestyle_general","route_reason":"생활습관"}'
    )
    answer_llm = _CountingLLM("혈당 생활습관 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("혈당 관리에 좋은 식사 원칙 알려줘", _rich_latest_analysis())

    assert msg.routed is False
    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == ["당화혈색소", "공복혈당"]
    assert len(answer_llm.calls) == 1
    assert "당화혈색소" in answer_llm.calls[0]["user"]
    assert "공복혈당" in answer_llm.calls[0]["user"]


def test_abdominal_obesity_lifestyle_question_uses_obesity_category_instead_of_short_alias_uncertain():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"lifestyle_general","route_reason":"생활습관"}'
    )
    answer_llm = _CountingLLM("비만 생활습관 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("복부비만이면 어떤 생활습관이 중요해?", _latest_analysis())

    assert msg.routed is False
    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == ["BMI"]
    assert len(answer_llm.calls) == 1
    assert "BMI" in answer_llm.calls[0]["user"]


def test_blood_pressure_category_question_uses_report_bp_items():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"lifestyle_general","route_reason":"생활습관"}'
    )
    answer_llm = _CountingLLM("혈압 생활습관 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("혈압 138에 86이면 생활습관을 어떻게 바꾸면 좋아요?", _rich_latest_analysis())

    assert msg.routed is False
    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == ["수축기혈압", "이완기혈압"]
    assert len(answer_llm.calls) == 1
    assert "수축기혈압" in answer_llm.calls[0]["user"]
    assert "이완기혈압" in answer_llm.calls[0]["user"]
    assert "내 수치 138.0 (caution)" in answer_llm.calls[0]["user"]
    assert "내 수치 86.0 (caution)" in answer_llm.calls[0]["user"]


def test_specific_blood_sugar_question_does_not_expand_to_category_items():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("공복혈당 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("공복혈당 92는 정상인가요?", _rich_latest_analysis())

    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == ["공복혈당"]
    assert "공복혈당" in answer_llm.calls[0]["user"]
    assert "당화혈색소" not in answer_llm.calls[0]["user"]


def test_specific_total_cholesterol_question_does_not_expand_to_lipid_items():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("총콜레스테롤 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("총콜레스테롤 225는 어떤 상태예요?", _rich_latest_analysis())

    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == ["총콜레스테롤"]
    assert "총콜레스테롤" in answer_llm.calls[0]["user"]
    assert "LDL 콜레스테롤" not in answer_llm.calls[0]["user"]
    assert "HDL 콜레스테롤" not in answer_llm.calls[0]["user"]
    assert "중성지방" not in answer_llm.calls[0]["user"]


def test_abbreviation_with_attached_korean_label_does_not_expand_to_category_items():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("LDL 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("LDL콜레스테롤 145는 어떤 상태예요?", _rich_latest_analysis())

    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == ["LDL 콜레스테롤"]
    assert "LDL 콜레스테롤" in answer_llm.calls[0]["user"]
    assert "총콜레스테롤" not in answer_llm.calls[0]["user"]
    assert "HDL 콜레스테롤" not in answer_llm.calls[0]["user"]
    assert "중성지방" not in answer_llm.calls[0]["user"]


def test_lipid_category_question_uses_report_lipid_items():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"lifestyle_general","route_reason":"생활습관"}'
    )
    answer_llm = _CountingLLM("지질 관리 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("콜레스테롤 관리는 어떻게 하면 좋아요?", _rich_latest_analysis())

    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == [
        "총콜레스테롤",
        "LDL 콜레스테롤",
        "HDL 콜레스테롤",
        "중성지방",
    ]


def test_gamma_gtp_spacing_and_typo_questions_use_report_item():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("감마지티피 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    for question in (
        "내 감마지티피 어때",
        "내 감마 지티피 어때",
        "내 감마지피티 어때",
        "gamma gtp 수치 어때",
    ):
        before_calls = len(answer_llm.calls)
        msg = service.answer(question, _gamma_latest_analysis())

        assert msg.route_reason == "rag_answer"
        assert msg.context_item_names == ["감마지티피"]
        assert len(answer_llm.calls) == before_calls + 1
        assert "감마지티피" in answer_llm.calls[-1]["user"]


def test_short_gamma_alias_is_allowed_only_when_item_exists_in_report():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("감마지티피 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    matched = service.answer("내 감마 어때", _gamma_latest_analysis())

    assert matched.route_reason == "rag_answer"
    assert matched.context_item_names == ["감마지티피"]
    assert len(answer_llm.calls) == 1

    missing = service.answer("내 감마 어때", _latest_analysis())

    assert missing.route_reason == "item_match_uncertain"
    assert missing.context_item_names == []
    assert missing.sources == []
    assert len(answer_llm.calls) == 1


def test_mixed_question_with_missing_alias_does_not_answer_partial_context():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("내 ALT랑 감마 어때", _latest_analysis())

    assert msg.route_reason == "item_match_uncertain"
    assert msg.context_item_names == []
    assert msg.sources == []
    assert answer_llm.calls == []


def test_mixed_question_with_joined_missing_alias_does_not_answer_partial_context():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    for question in (
        "내 ALT랑감마 어때",
        "ALT와갑상선 같이 봐줘",
        "BMI랑전립선 어때",
    ):
        msg = service.answer(question, _latest_analysis())

        assert msg.route_reason == "item_match_uncertain", question
        assert msg.context_item_names == [], question
        assert msg.sources == [], question

    assert answer_llm.calls == []


def test_mixed_question_with_concatenated_missing_alias_does_not_answer_partial_context():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    for question in (
        "ALT감마 같이 봐줘",
        "BMI전립선 같이 봐줘",
    ):
        msg = service.answer(question, _latest_analysis())

        assert msg.route_reason == "item_match_uncertain", question
        assert msg.context_item_names == [], question
        assert msg.sources == [], question

    assert answer_llm.calls == []


def test_mixed_question_with_report_gated_alias_answers_all_matched_items():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("간수치 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("내 ALT랑 감마 어때", _gamma_latest_analysis())

    assert msg.route_reason == "rag_answer"
    assert msg.context_item_names == ["ALT", "감마지티피"]
    assert len(answer_llm.calls) == 1


def test_long_official_synonym_can_be_reference_only_when_missing_from_report():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("eGFR 설명")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("estimated glomerular filtration rate 수치 어때", _latest_analysis())

    assert msg.route_reason == "reference_only_answer"
    assert msg.context_item_names == ["eGFR"]
    assert len(answer_llm.calls) == 1


def test_long_official_synonym_with_korean_particle_can_be_reference_only():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("일반 정보")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    cases = [
        ("total cholesterol이 뭐야", "총콜레스테롤"),
        ("estimated glomerular filtration rate가 뭐야", "eGFR"),
    ]
    for question, expected_item in cases:
        before_calls = len(answer_llm.calls)
        msg = service.answer(question, _latest_analysis())

        assert msg.route_reason == "reference_only_answer"
        assert msg.context_item_names == [expected_item]
        assert len(answer_llm.calls) == before_calls + 1


def test_gamma_like_unrelated_terms_do_not_match_or_fallback_to_report_items():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    for question in ("감마선이 뭐야", "지피티가 뭐야"):
        msg = service.answer(question, _gamma_latest_analysis())

        assert msg.route_reason == "item_match_uncertain"
        assert msg.context_item_names == []
        assert msg.sources == []

    symptom_like = service.answer("감기 때문에 힘들어", _gamma_latest_analysis())

    assert symptom_like.route_reason in ("no_grounding", "item_match_uncertain")
    assert symptom_like.context_item_names == []
    assert symptom_like.sources == []
    assert answer_llm.calls == []


def test_ambiguous_fuzzy_candidates_do_not_choose_one_item():
    classifier_llm = _CountingLLM(
        '{"scope":"allowed","question_type":"checkup_explanation","route_reason":"수치 설명"}'
    )
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )

    msg = service.answer("cholesterol 수치 어때", _rich_latest_analysis())

    assert msg.route_reason == "item_match_uncertain"
    assert msg.context_item_names == []
    assert msg.sources == []
    assert answer_llm.calls == []
