"""F-007 챗봇 - 질문 스코프 분류 및 라우팅 (LLM 포트 주입)

흐름: 규칙 하드 차단 → LLM 분류(모호하면 비허용) → 비허용은 전문의 상담 라우팅
답변 생성(공인 출처 RAG)은 다음 단계 - 본 모듈은 안전 게이트(분류·라우팅)만 담당
"""

import json

from gogodoc.application.ports import LLMPort, LLMTask
from gogodoc.application import prompts
from gogodoc.domain import chat_scope
from gogodoc.domain.models import ChatMessage, QuestionType, Scope, ScopeDecision


def _legacy_label_decision(text: str) -> ScopeDecision:
    """기존 '허용'/'비허용' 한 단어 응답을 보수적으로 해석"""
    out = (text or "").strip()
    if out == "허용":
        return ScopeDecision(
            scope=Scope.ALLOWED,
            routed=False,
            reason="llm",
            question_type=QuestionType.UNKNOWN,
            route_reason="legacy_allowed_label",
        )
    return ScopeDecision(
        scope=Scope.BLOCKED,
        routed=True,
        reason="llm",
        question_type=QuestionType.UNKNOWN,
        route_reason="legacy_blocked_or_invalid_label",
    )


def _parse_json_decision(text: str) -> ScopeDecision | None:
    """구조화된 LLM 분류 결과를 ScopeDecision으로 변환"""
    try:
        payload = json.loads((text or "").strip())
    except json.JSONDecodeError:
        return None
    if not isinstance(payload, dict):
        return None

    try:
        question_type = QuestionType(str(payload.get("question_type") or ""))
    except ValueError:
        return ScopeDecision(
            scope=Scope.BLOCKED,
            routed=True,
            reason="llm",
            question_type=QuestionType.UNKNOWN,
            route_reason="invalid_question_type",
        )

    scope = chat_scope.scope_for_question_type(question_type)
    raw_scope = str(payload.get("scope") or "").strip()
    if raw_scope and raw_scope != scope.value:
        return ScopeDecision(
            scope=Scope.BLOCKED,
            routed=True,
            reason="llm",
            question_type=QuestionType.UNKNOWN,
            route_reason="scope_type_mismatch",
        )

    return ScopeDecision(
        scope=scope,
        routed=scope == Scope.BLOCKED,
        reason="llm",
        question_type=question_type,
        route_reason=str(payload.get("route_reason") or "llm_classifier").strip(),
    )


def _parse_decision(text: str) -> ScopeDecision:
    """LLM 분류 출력을 fail-closed 방식으로 해석"""
    structured = _parse_json_decision(text)
    if structured is not None:
        return structured
    return _legacy_label_decision(text)


class ChatService:
    """챗봇 질문 분류·라우팅 - 안전 게이트"""

    def __init__(self, llm: LLMPort) -> None:
        self._llm = llm

    def classify(self, question: str) -> ScopeDecision:
        """질문 스코프 판정 - 규칙 하드차단 우선, 그 외 LLM, 모호·실패 시 비허용(보수적)"""
        # 1) 규칙 하드 라우팅 - 명백한 위험·범위밖·미지원 유형
        rule_decision = chat_scope.classify_rule_detail(question)
        if rule_decision is not None:
            return rule_decision

        # 2) LLM 분류 - 실패 시 보수적으로 차단
        try:
            out = self._llm.complete(
                system=prompts.CHAT_SCOPE_SYSTEM, user=question, task=LLMTask.CLASSIFY
            )
        except Exception:
            return ScopeDecision(
                scope=Scope.BLOCKED,
                routed=True,
                reason="llm_error",
                question_type=QuestionType.UNKNOWN,
                route_reason="classifier_exception",
            )

        return _parse_decision(out)

    def route(self, question: str) -> ChatMessage | None:
        """비허용 질문이면 전문의 상담 안내 메시지 반환, 허용이면 None(답변 단계로 위임)"""
        decision = self.classify(question)
        return self.route_decision(decision)

    def route_decision(self, decision: ScopeDecision) -> ChatMessage | None:
        """분류 결과가 차단이면 안내 메시지를 반환하고 허용이면 None 반환"""
        if decision.scope != Scope.BLOCKED:
            return None
        return ChatMessage(
            role="assistant",
            content=chat_scope.routing_message(decision.question_type),
            scope_flag=Scope.BLOCKED,
            routed=True,
            question_type=decision.question_type,
            route_reason=decision.route_reason,
        )
