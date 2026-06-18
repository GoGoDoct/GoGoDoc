"""F-007 ChatService 분류·라우팅 테스트 - 가짜 LLM 주입 (API 불필요)"""

from gogodoc.application.chat_service import ChatService
from gogodoc.application.ports import LLMTask
from gogodoc.domain.models import QuestionType, Scope


class _FakeLLM:
    """고정 라벨 반환 가짜 LLM"""

    def __init__(self, label: str):
        self.label = label

    def complete(self, system, user, task: LLMTask) -> str:
        return self.label


class _BoomLLM:
    """예외 발생 가짜 LLM - 보수적 차단 검증"""

    def complete(self, system, user, task: LLMTask) -> str:
        raise RuntimeError("LLM 실패")


def test_rule_block_overrides_llm():
    # 규칙 하드 차단이면 LLM 이 허용이라 해도 BLOCKED (안전 우선)
    svc = ChatService(_FakeLLM("허용"))
    d = svc.classify("무슨 약을 먹어야 하나요?")
    assert d.scope == Scope.BLOCKED and d.routed and d.reason == "rule"


def test_llm_allowed():
    svc = ChatService(_FakeLLM('{"scope":"allowed","question_type":"checkup_explanation","route_reason":"항목 설명"}'))
    d = svc.classify("검진에서 나온 항목을 쉽게 설명해줘")
    assert d.scope == Scope.ALLOWED and not d.routed and d.reason == "llm"
    assert d.question_type == QuestionType.CHECKUP_EXPLANATION


def test_llm_blocked():
    svc = ChatService(_FakeLLM('{"scope":"blocked","question_type":"diagnosis_request","route_reason":"진단 요청"}'))
    d = svc.classify("이 수치면 큰 병인가요?")
    assert d.scope == Scope.BLOCKED and d.routed
    assert d.question_type == QuestionType.DIAGNOSIS_REQUEST


def test_legacy_label_allowed_still_supported():
    svc = ChatService(_FakeLLM("허용"))
    d = svc.classify("검진 결과를 쉽게 설명해줘")
    assert d.scope == Scope.ALLOWED
    assert d.question_type == QuestionType.UNKNOWN


def test_invalid_or_ambiguous_label_is_blocked():
    # '허용하지 않음'처럼 허용을 포함한 모호한 출력은 fail-closed
    svc = ChatService(_FakeLLM("허용하지 않음"))
    d = svc.classify("애매한 질문입니다")
    assert d.scope == Scope.BLOCKED
    assert d.question_type == QuestionType.UNKNOWN


def test_json_scope_type_mismatch_is_blocked():
    svc = ChatService(_FakeLLM('{"scope":"allowed","question_type":"emergency_symptom","route_reason":"불일치"}'))
    d = svc.classify("애매한 질문입니다")
    assert d.scope == Scope.BLOCKED
    assert d.question_type == QuestionType.UNKNOWN


def test_llm_error_is_conservative():
    # LLM 실패 시 보수적으로 차단
    svc = ChatService(_BoomLLM())
    d = svc.classify("애매한 질문입니다")
    assert d.scope == Scope.BLOCKED and d.reason == "llm_error"


def test_route_returns_message_only_when_blocked():
    blocked = ChatService(_FakeLLM("비허용")).route("저 당뇨병인가요?")
    assert blocked is not None and blocked.routed and blocked.role == "assistant"
    allowed = ChatService(_FakeLLM("허용")).route("ALT가 뭐예요?")
    assert allowed is None


def test_emergency_route_message_is_specific_and_skips_llm():
    svc = ChatService(_FakeLLM("허용"))
    msg = svc.route("가슴이 답답하고 숨이 차요")
    assert msg is not None
    assert msg.scope_flag == Scope.BLOCKED
    assert msg.question_type == QuestionType.EMERGENCY_SYMPTOM
    assert "119" in msg.content


def test_common_real_checkup_item_phrases_skip_llm_classifier():
    # 실제 사용자 말투의 검진 항목 질문은 LLM 분류기가 실패해도 rule 단계에서 허용한다.
    svc = ChatService(_BoomLLM())

    for question in [
        "AST 수치도 같이 봐줘",
        "내 감마 지티피 어때",
        "내 감마지피티 어때",
        "triglycerides 수치 봐줘",
        "헤모글로빈 수치 봐줘",
        "내 허리 어때",
        "갑상선 수치 봐줘",
        "전립선 수치 어때",
    ]:
        d = svc.classify(question)

        assert d.scope == Scope.ALLOWED, question
        assert d.routed is False, question
        assert d.reason == "rule", question
        assert d.question_type == QuestionType.CHECKUP_EXPLANATION, question
        assert d.route_reason == "checkup_item_rule", question
