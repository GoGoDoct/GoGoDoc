"""F-007 챗봇 답변 통합 - 안전 게이트 통과 후 RAG 답변 생성."""

import json
from collections.abc import Mapping, Sequence
from typing import Any, Protocol

from gogodoc.application.chat_service import ChatService
from gogodoc.domain.models import (
    ChatMessage,
    FinalReport,
    Flag,
    InterpretedItem,
    QuestionType,
    Scope,
    ScopeDecision,
    UserProfile,
)
from gogodoc.domain.policy import DISCLAIMER
from gogodoc.domain.services.safety import sanitize_text


_STATUS_TO_FLAG = {
    "정상": Flag.NORMAL,
    "주의": Flag.CAUTION,
    "이상": Flag.ABNORMAL,
    "응급": Flag.EMERGENCY,
    "확인필요": Flag.CHECK_NEEDED,
}

_NO_RESULT = "최신 검진 결과가 없어 답변할 수 없습니다. 먼저 검진 결과지를 업로드해 주세요."
_RAG_FAILURE = "답변 생성에 실패했습니다. 잠시 후 다시 시도하시거나 전문의 상담을 권장합니다."


class RagAnswerPort(Protocol):
    """허용 질문 답변 생성 포트."""

    def answer(
        self,
        question: str,
        report: FinalReport | None = None,
        profile: UserProfile | None = None,
    ) -> ChatMessage:
        """질문과 검진 리포트를 사용해 답변 메시지를 생성한다."""


def _with_disclaimer(text: str, *, sanitize: bool = True) -> str:
    """안전 필터를 적용하고 표준 면책 문구를 보강한다."""
    raw = (text or "").strip()
    clean = sanitize_text(raw) if sanitize else raw
    if DISCLAIMER in clean:
        return clean
    return f"{clean}\n\n{DISCLAIMER}" if clean else DISCLAIMER


def _json_list(value: Any) -> list[Any]:
    """DB JSON/JSONB 컬럼 값을 리스트로 정규화한다."""
    if value is None:
        return []
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        return parsed if isinstance(parsed, list) else []
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return list(value)
    return []


def _text_list(value: Any) -> list[str]:
    """DB JSON/JSONB 텍스트 배열 값을 문자열 리스트로 정규화한다."""
    result: list[str] = []
    for item in _json_list(value):
        text = str(item).strip()
        if text:
            result.append(text)
    return result


def _to_float(value: Any) -> float | None:
    """저장된 수치 값을 float로 변환하되 실패하면 알 수 없음으로 둔다."""
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        return float(str(value).replace(",", "").strip())
    except ValueError:
        return None


def _to_flag(status: Any) -> Flag:
    """저장된 한글 상태 또는 Flag value를 도메인 Flag로 변환한다."""
    text = str(status or "").strip()
    if text in _STATUS_TO_FLAG:
        return _STATUS_TO_FLAG[text]
    try:
        return Flag(text)
    except ValueError:
        return Flag.UNKNOWN


def _to_report(latest_analysis: Mapping[str, Any] | FinalReport) -> FinalReport:
    """latest analysis row의 items_json을 RAG 서비스가 쓰는 FinalReport로 변환한다."""
    if isinstance(latest_analysis, FinalReport):
        return latest_analysis

    interpreted: list[InterpretedItem] = []
    for raw in _json_list(latest_analysis.get("items_json")):
        if not isinstance(raw, Mapping):
            continue
        name = str(raw.get("name") or "").strip()
        if not name:
            continue
        value = _to_float(raw.get("value", raw.get("value_text")))
        interpreted.append(
            InterpretedItem(
                canonical_name=name,
                raw_name=name,
                value=value,
                unit=raw.get("unit"),
                flag=_to_flag(raw.get("status")),
                matched=True,
                explanation=str(raw.get("explain") or raw.get("explanation") or ""),
                source=raw.get("source"),
            )
        )

    return FinalReport(
        items=interpreted,
        tracking_items=_text_list(latest_analysis.get("tracking_items")),
        emergency_alerts=_text_list(latest_analysis.get("emergency_alerts")),
    )


def _status_text(flag: Flag) -> str:
    """도메인 Flag를 사용자에게 보여줄 한글 상태로 변환"""
    return {
        Flag.NORMAL: "정상",
        Flag.CAUTION: "주의",
        Flag.ABNORMAL: "이상",
        Flag.EMERGENCY: "응급",
        Flag.CHECK_NEEDED: "확인필요",
        Flag.UNKNOWN: "알수없음",
    }.get(flag, flag.value)


def _build_summary_message(report: FinalReport) -> ChatMessage:
    """최신 검진 결과 1건을 기반으로 결정적 요약 메시지를 만든다."""
    flagged = [it for it in report.items if it.flag in (Flag.CAUTION, Flag.ABNORMAL, Flag.EMERGENCY)]
    sources: list[str] = []
    for item in flagged:
        if item.source and item.source not in sources:
            sources.append(item.source)

    lines: list[str] = []
    if report.emergency_alerts:
        lines.append("응급으로 확인된 항목이 있어 즉시 의료기관 상담이 필요합니다.")
        lines.extend(report.emergency_alerts[:2])
    if flagged:
        names = ", ".join(f"{it.canonical_name}({_status_text(it.flag)})" for it in flagged[:5])
        lines.append(f"최신 검진 결과에서 우선 확인할 항목은 {names}입니다.")
    elif report.items:
        lines.append("최신 검진 결과에서 주의·이상·응급으로 분류된 항목은 확인되지 않았습니다.")
    else:
        lines.append("최신 검진 결과에서 요약할 검사 항목을 찾지 못했습니다.")
    if report.tracking_items:
        lines.append(f"추적 관찰 항목은 {', '.join(report.tracking_items[:5])}입니다.")
    lines.append("각 항목의 의미나 관리 방법은 항목명을 포함해 다시 질문하면 더 구체적으로 안내할 수 있습니다.")

    return ChatMessage(
        role="assistant",
        content=" ".join(lines),
        scope_flag=Scope.ALLOWED,
        routed=False,
        sources=sources,
        context_item_names=[it.canonical_name for it in flagged],
        question_type=QuestionType.CHECKUP_SUMMARY,
        route_reason="summary_answer",
    )


class ChatAnswerService:
    """안전 게이트와 RAG 답변을 연결하는 F-007 챗봇 애플리케이션 서비스."""

    def __init__(self, router: ChatService, rag: RagAnswerPort) -> None:
        self._router = router
        self._rag = rag

    def answer(
        self,
        question: str,
        latest_analysis: Mapping[str, Any] | FinalReport | None,
        profile: UserProfile | None = None,
    ) -> ChatMessage:
        """질문 안전성 확인 후 허용 질문만 최신 검진 결과 기반 RAG 답변으로 전달한다."""
        decision = self.classify(question)
        routed = self.route_decision(decision)
        if routed is not None:
            return routed

        return self.answer_allowed(question, latest_analysis, profile=profile, decision=decision)

    def classify(self, question: str) -> ScopeDecision:
        """질문 안전성 및 세부 유형을 분류한다."""
        return self._router.classify(question)

    def route(self, question: str) -> ChatMessage | None:
        """차단 질문이면 라우팅 메시지를 반환하고, 허용 질문이면 None을 반환한다."""
        return self.route_decision(self.classify(question))

    def route_decision(self, decision: ScopeDecision) -> ChatMessage | None:
        """분류 결과가 차단이면 라우팅 메시지를 반환하고, 허용이면 None을 반환한다."""
        routed = self._router.route_decision(decision)
        if routed is None:
            return None
        return routed.model_copy(update={"content": _with_disclaimer(routed.content, sanitize=False)})

    def answer_allowed(
        self,
        question: str,
        latest_analysis: Mapping[str, Any] | FinalReport | None,
        profile: UserProfile | None = None,
        decision: ScopeDecision | None = None,
    ) -> ChatMessage:
        """허용 질문에 대해 최신 검진 결과 기반 RAG 답변을 생성한다."""
        if latest_analysis is None:
            return ChatMessage(
                role="assistant",
                content=_with_disclaimer(_NO_RESULT),
                scope_flag=Scope.ALLOWED,
                routed=True,
                question_type=decision.question_type if decision else QuestionType.UNKNOWN,
                route_reason="missing_latest_analysis",
            )

        report = _to_report(latest_analysis)
        if decision and decision.question_type == QuestionType.CHECKUP_SUMMARY:
            answered = _build_summary_message(report)
            return answered.model_copy(update={"content": _with_disclaimer(answered.content)})

        try:
            answered = self._rag.answer(question, report=report, profile=profile)
        except Exception:
            answered = ChatMessage(
                role="assistant",
                content=_RAG_FAILURE,
                scope_flag=Scope.ALLOWED,
                question_type=decision.question_type if decision else QuestionType.UNKNOWN,
                route_reason="rag_exception",
            )

        updates: dict[str, Any] = {"content": _with_disclaimer(answered.content)}
        if decision and answered.question_type is None:
            updates["question_type"] = decision.question_type
        if decision and not answered.route_reason:
            updates["route_reason"] = decision.route_reason or "rag_answer"
        return answered.model_copy(update=updates)
