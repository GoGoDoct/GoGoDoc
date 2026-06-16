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
    Scope,
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


def _with_disclaimer(text: str) -> str:
    """안전 필터를 적용하고 표준 면책 문구를 보강한다."""
    clean = sanitize_text((text or "").strip())
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
        routed = self.route(question)
        if routed is not None:
            return routed

        return self.answer_allowed(question, latest_analysis, profile=profile)

    def route(self, question: str) -> ChatMessage | None:
        """차단 질문이면 라우팅 메시지를 반환하고, 허용 질문이면 None을 반환한다."""
        routed = self._router.route(question)
        if routed is None:
            return None
        return routed.model_copy(update={"content": _with_disclaimer(routed.content)})

    def answer_allowed(
        self,
        question: str,
        latest_analysis: Mapping[str, Any] | FinalReport | None,
        profile: UserProfile | None = None,
    ) -> ChatMessage:
        """허용 질문에 대해 최신 검진 결과 기반 RAG 답변을 생성한다."""
        if latest_analysis is None:
            return ChatMessage(
                role="assistant",
                content=_with_disclaimer(_NO_RESULT),
                scope_flag=Scope.ALLOWED,
                routed=True,
            )

        report = _to_report(latest_analysis)
        try:
            answered = self._rag.answer(question, report=report, profile=profile)
        except Exception:
            answered = ChatMessage(
                role="assistant",
                content=_RAG_FAILURE,
                scope_flag=Scope.ALLOWED,
            )

        return answered.model_copy(update={"content": _with_disclaimer(answered.content)})
