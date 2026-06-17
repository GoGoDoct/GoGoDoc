"""F-007 챗봇 UI 호출 계약.

Streamlit 화면은 이 모듈의 payload만 받아 표시하고, DB 조회와 답변 서비스 호출 순서는
애플리케이션 계층에서 고정한다.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from gogodoc.application.chat_answer_service import ChatAnswerService
from gogodoc.domain.models import ChatMessage, UserProfile


LatestAnalysisReader = Callable[[Any, int], Mapping[str, Any] | None]


class ChatUiContract:
    """UI가 호출할 최신 검진 결과 기반 챗봇 계약."""

    def __init__(
        self,
        *,
        answer_service: ChatAnswerService,
        latest_reader: LatestAnalysisReader,
    ) -> None:
        self._answer_service = answer_service
        self._latest_reader = latest_reader

    def answer_latest(
        self,
        *,
        conn: Any,
        user_id: int,
        question: str,
        profile: UserProfile | None = None,
    ) -> dict[str, Any]:
        """최신 분석 결과 1건을 읽어 챗봇 답변 UI payload로 변환한다."""
        decision = self._answer_service.classify(question)
        routed = self._answer_service.route_decision(decision)
        if routed is not None:
            return _to_payload(
                routed,
                latest_analysis=None,
                latest_analysis_checked=False,
            )

        latest_analysis = self._latest_reader(conn, user_id)
        message = self._answer_service.answer_allowed(
            question,
            latest_analysis,
            profile=profile,
            decision=decision,
        )
        return _to_payload(
            message,
            latest_analysis=latest_analysis,
            latest_analysis_checked=True,
        )


def _to_payload(
    message: ChatMessage,
    *,
    latest_analysis: Mapping[str, Any] | None,
    latest_analysis_checked: bool,
) -> dict[str, Any]:
    """ChatMessage와 최신 분석 메타데이터를 UI 표시용 dict로 변환한다."""
    has_latest_analysis = latest_analysis is not None if latest_analysis_checked else None
    return {
        "content": message.content,
        "scope_flag": message.scope_flag.value if message.scope_flag else None,
        "routed": message.routed,
        "question_type": message.question_type.value if message.question_type else None,
        "route_reason": message.route_reason,
        "sources": list(message.sources),
        "context_item_names": list(message.context_item_names),
        "latest_analysis_checked": latest_analysis_checked,
        "has_latest_analysis": has_latest_analysis,
        "analysis_id": latest_analysis.get("id") if latest_analysis else None,
        "analysis_filename": latest_analysis.get("filename") if latest_analysis else None,
    }
