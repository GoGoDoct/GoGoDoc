"""F-007 챗봇 - 질문 스코프 분류 및 라우팅 (LLM 포트 주입)

흐름: 규칙 하드 차단 → LLM 분류(모호하면 비허용) → 비허용은 전문의 상담 라우팅
답변 생성(공인 출처 RAG)은 다음 단계 - 본 모듈은 안전 게이트(분류·라우팅)만 담당
"""

from gogodoc.application.ports import LLMPort, LLMTask
from gogodoc.application import prompts
from gogodoc.domain import chat_scope
from gogodoc.domain.models import Scope, ScopeDecision, ChatMessage


def _parse_label(text: str) -> bool:
    """LLM 출력에서 허용 여부 파싱 - '비허용'이 '허용'을 포함하므로 비허용 우선 검사"""
    out = (text or "").strip()
    return "비허용" not in out and "허용" in out


class ChatService:
    """챗봇 질문 분류·라우팅 - 안전 게이트"""

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def classify(self, question: str) -> ScopeDecision:
        """질문 스코프 판정 - 규칙 하드차단 우선, 그 외 LLM, 모호·실패 시 비허용(보수적)"""
        # 1) 규칙 하드 차단 - 명백한 진단·처방·복약
        if chat_scope.classify_rule(question) == Scope.BLOCKED:
            return ScopeDecision(scope=Scope.BLOCKED, routed=True, reason="rule")

        # 2) LLM 분류 - 실패 시 보수적으로 차단
        try:
            out = self._llm.complete(
                system=prompts.CHAT_SCOPE_SYSTEM, user=question, task=LLMTask.CLASSIFY
            )
        except Exception:
            return ScopeDecision(scope=Scope.BLOCKED, routed=True, reason="llm_error")

        if _parse_label(out):
            return ScopeDecision(scope=Scope.ALLOWED, routed=False, reason="llm")
        return ScopeDecision(scope=Scope.BLOCKED, routed=True, reason="llm")

    def route(self, question: str) -> ChatMessage | None:
        """비허용 질문이면 전문의 상담 안내 메시지 반환, 허용이면 None(답변 단계로 위임)"""
        decision = self.classify(question)
        if decision.scope == Scope.BLOCKED:
            return ChatMessage(
                role="assistant",
                content=chat_scope.ROUTING_MESSAGE,
                scope_flag=Scope.BLOCKED,
                routed=True,
            )
        return None
