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
    assert msg.question_type == QuestionType.UNKNOWN
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
