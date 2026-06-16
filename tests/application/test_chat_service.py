"""F-007 ChatService 분류·라우팅 테스트 - 가짜 LLM 주입 (API 불필요)"""

from gogodoc.application.chat_service import ChatService
from gogodoc.application.ports import LLMTask
from gogodoc.domain.models import Scope


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
    svc = ChatService(_FakeLLM("허용"))
    d = svc.classify("ALT가 60인데 무슨 의미예요?")
    assert d.scope == Scope.ALLOWED and not d.routed and d.reason == "llm"


def test_llm_blocked():
    # '비허용'이 '허용'을 부분문자로 포함해도 정확히 차단 파싱
    svc = ChatService(_FakeLLM("비허용"))
    d = svc.classify("이 수치면 큰 병인가요?")
    assert d.scope == Scope.BLOCKED and d.routed


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
