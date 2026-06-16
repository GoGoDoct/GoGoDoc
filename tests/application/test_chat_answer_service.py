"""F-007 챗봇 답변 서비스 테스트 - 안전게이트 이후 최신 결과 컨텍스트"""

from gogodoc.application.chat_answer_service import ChatAnswerService
from gogodoc.application.chat_service import ChatService
from gogodoc.application.ports import LLMTask
from gogodoc.domain.models import Scope
from gogodoc.domain.policy import DISCLAIMER
from gogodoc.infrastructure.retrieval.dict_retriever import DictRetriever


class _CountingLLM:
    """호출 내용을 기록하는 가짜 LLM"""

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
                "unit": "kg/m²",
                "status": "이상",
                "explain": "키 대비 체중으로 비만 정도를 보는 체질량지수입니다.",
                "source": "대한비만학회 비만 진료지침",
            },
        ],
    }


def test_blocked_question_returns_routing_without_answer_llm():
    classifier_llm = _CountingLLM("허용")
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        answer_llm=answer_llm,
        retriever=DictRetriever(),
    )

    msg = service.answer("무슨 약을 먹어야 하나요?", _latest_analysis())

    assert msg.routed is True
    assert msg.scope_flag == Scope.BLOCKED
    assert "전문의" in msg.content
    assert DISCLAIMER in msg.content
    assert classifier_llm.calls == []
    assert answer_llm.calls == []


def test_allowed_question_uses_latest_result_and_category_guide_sources():
    classifier_llm = _CountingLLM("허용")
    answer_llm = _CountingLLM("BMI는 체중과 키의 관계를 보는 지표입니다.")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        answer_llm=answer_llm,
        retriever=DictRetriever(),
    )

    msg = service.answer("BMI가 높으면 어떻게 관리해요?", _latest_analysis())

    assert msg.routed is False
    assert msg.scope_flag == Scope.ALLOWED
    assert msg.context_item_names == ["BMI"]
    assert "대한비만학회 비만 진료지침" in msg.sources
    assert DISCLAIMER in msg.content

    assert len(answer_llm.calls) == 1
    call = answer_llm.calls[0]
    assert call["task"] == LLMTask.INTERPRET
    assert "BMI" in call["user"]
    assert "27.1 kg/m²" in call["user"]
    assert "비만" in call["user"]
    assert "균형 잡힌 식사" in call["user"]
    assert "대한비만학회 비만 진료지침" in call["user"]
    assert "ALT" not in call["user"]


def test_missing_latest_result_returns_guidance_without_answer_llm():
    classifier_llm = _CountingLLM("허용")
    answer_llm = _CountingLLM("부르면 안 되는 답변")
    service = ChatAnswerService(
        router=ChatService(classifier_llm),
        answer_llm=answer_llm,
        retriever=DictRetriever(),
    )

    msg = service.answer("ALT가 무슨 뜻이에요?", None)

    assert msg.routed is True
    assert "최신 검진 결과" in msg.content
    assert DISCLAIMER in msg.content
    assert answer_llm.calls == []
