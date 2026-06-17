"""F-007 챗봇 UI 호출 계약 테스트."""

from gogodoc.application.chat_answer_service import ChatAnswerService
from gogodoc.application.chat_rag_service import ChatRagService
from gogodoc.application.chat_service import ChatService
from gogodoc.application.chat_ui_contract import ChatUiContract
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
        "id": 7,
        "filename": "sample.pdf",
        "tracking_items": ["BMI"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "BMI",
                "value": 27.1,
                "value_text": "27.1",
                "unit": "kg/m2",
                "status": "이상",
                "explain": "키 대비 체중으로 비만 정도를 보는 체질량지수입니다.",
                "source": "대한비만학회 비만 진료지침",
            }
        ],
    }


def _contract(latest_analysis, classifier_response="허용", answer_response="BMI 답변"):
    classifier_llm = _CountingLLM(classifier_response)
    answer_llm = _CountingLLM(answer_response)
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )
    contract = ChatUiContract(
        answer_service=service,
        latest_reader=lambda conn, user_id: latest_analysis,
    )
    return contract, classifier_llm, answer_llm


def _contract_with_reader(latest_reader, classifier_response="허용", answer_response="BMI 답변"):
    classifier_llm = _CountingLLM(classifier_response)
    answer_llm = _CountingLLM(answer_response)
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        rag=ChatRagService(answer_llm),
    )
    contract = ChatUiContract(
        answer_service=service,
        latest_reader=latest_reader,
    )
    return contract, classifier_llm, answer_llm


def test_allowed_question_returns_ui_payload_with_grounding_fields():
    contract, _classifier_llm, answer_llm = _contract(_latest_analysis())

    payload = contract.answer_latest(
        conn=object(),
        user_id=1,
        question="BMI가 높으면 어떻게 관리해요?",
    )

    assert payload["has_latest_analysis"] is True
    assert payload["latest_analysis_checked"] is True
    assert payload["scope_flag"] == Scope.ALLOWED.value
    assert payload["routed"] is False
    assert payload["question_type"] == QuestionType.UNKNOWN.value
    assert payload["route_reason"]
    assert payload["context_item_names"] == ["BMI"]
    assert any("대한비만학회" in source for source in payload["sources"])
    assert DISCLAIMER in payload["content"]
    assert payload["analysis_id"] == 7
    assert payload["analysis_filename"] == "sample.pdf"
    assert len(answer_llm.calls) == 1


def test_blocked_question_routes_before_latest_reader_and_answer_llm_call():
    def fail_if_called(conn, user_id):
        raise AssertionError("차단 질문에서는 최신 분석 결과를 조회하면 안 된다")

    contract, classifier_llm, answer_llm = _contract_with_reader(fail_if_called)

    payload = contract.answer_latest(
        conn=object(),
        user_id=1,
        question="무슨 약을 먹어야 하나요?",
    )

    assert payload["latest_analysis_checked"] is False
    assert payload["has_latest_analysis"] is None
    assert payload["scope_flag"] == Scope.BLOCKED.value
    assert payload["routed"] is True
    assert payload["question_type"] == QuestionType.PRESCRIPTION_REQUEST.value
    assert payload["route_reason"] == "prescription_rule"
    assert "전문의" in payload["content"]
    assert DISCLAIMER in payload["content"]
    assert payload["context_item_names"] == []
    assert payload["sources"] == []
    assert classifier_llm.calls == []
    assert answer_llm.calls == []


def test_missing_latest_analysis_returns_guidance_payload():
    contract, _classifier_llm, answer_llm = _contract(None)

    payload = contract.answer_latest(
        conn=object(),
        user_id=1,
        question="ALT가 무슨 뜻이에요?",
    )

    assert payload["has_latest_analysis"] is False
    assert payload["latest_analysis_checked"] is True
    assert payload["scope_flag"] == Scope.ALLOWED.value
    assert payload["routed"] is True
    assert payload["question_type"] == QuestionType.UNKNOWN.value
    assert payload["route_reason"] == "missing_latest_analysis"
    assert "최신 검진 결과" in payload["content"]
    assert DISCLAIMER in payload["content"]
    assert payload["context_item_names"] == []
    assert payload["sources"] == []
    assert payload["analysis_id"] is None
    assert payload["analysis_filename"] is None
    assert answer_llm.calls == []


def test_emergency_question_routes_before_latest_reader():
    def fail_if_called(conn, user_id):
        raise AssertionError("응급 질문에서는 최신 분석 결과를 조회하면 안 된다")

    contract, classifier_llm, answer_llm = _contract_with_reader(fail_if_called)

    payload = contract.answer_latest(
        conn=object(),
        user_id=1,
        question="가슴이 답답하고 숨이 차요",
    )

    assert payload["latest_analysis_checked"] is False
    assert payload["has_latest_analysis"] is None
    assert payload["scope_flag"] == Scope.BLOCKED.value
    assert payload["routed"] is True
    assert payload["question_type"] == QuestionType.EMERGENCY_SYMPTOM.value
    assert "119" in payload["content"]
    assert classifier_llm.calls == []
    assert answer_llm.calls == []
