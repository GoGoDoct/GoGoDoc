"""F-007 챗봇 답변 생성 - 안전게이트 통과 후 최신 검진 결과 컨텍스트 사용"""

from collections.abc import Mapping
from typing import Any

from gogodoc.application.chat_service import ChatService
from gogodoc.application.ports import LLMPort, LLMTask, ReferenceRetrieverPort
from gogodoc.application import prompts
from gogodoc.domain.models import ChatMessage, Scope
from gogodoc.domain.policy import DISCLAIMER
from gogodoc.domain.reference import category_guide
from gogodoc.domain.services.safety import sanitize_text


_FLAGGED_STATUS = {"주의", "이상", "응급"}


def _with_disclaimer(text: str) -> str:
    """면책 문구 보강"""
    clean = sanitize_text((text or "").strip())
    if DISCLAIMER in clean:
        return clean
    return f"{clean}\n\n{DISCLAIMER}" if clean else DISCLAIMER


def _dedupe(values: list[str]) -> list[str]:
    """순서 유지 중복 제거"""
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if not value or value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


class ChatAnswerService:
    """질문 라우팅 후 허용 질문에만 검진 결과 기반 답변 생성"""

    def __init__(
        self,
        router: ChatService,
        answer_llm: LLMPort,
        retriever: ReferenceRetrieverPort,
    ) -> None:
        self._router = router
        self._answer_llm = answer_llm
        self._retriever = retriever

    def answer(self, question: str, latest_analysis: Mapping[str, Any] | None) -> ChatMessage:
        """F-007 답변 생성 - 차단 질문은 답변 생성 LLM 호출 없이 라우팅"""
        routed = self._router.route(question)
        if routed is not None:
            return routed.model_copy(update={"content": _with_disclaimer(routed.content)})

        if not latest_analysis:
            return ChatMessage(
                role="assistant",
                content=_with_disclaimer("최신 검진 결과가 없어 답변할 수 없습니다. 먼저 검진 결과지를 업로드해 주세요."),
                scope_flag=Scope.ALLOWED,
                routed=True,
            )

        items = self._select_items(question, latest_analysis)
        if not items:
            return ChatMessage(
                role="assistant",
                content=_with_disclaimer("질문과 연결할 수 있는 검진 항목을 찾지 못했습니다. 결과 화면의 항목명을 포함해 다시 질문해 주세요."),
                scope_flag=Scope.ALLOWED,
                routed=True,
            )

        prompt, sources, item_names = self._build_user_prompt(question, items)
        text = self._answer_llm.complete(
            system=prompts.CHAT_ANSWER_SYSTEM,
            user=prompt,
            task=LLMTask.INTERPRET,
        )
        return ChatMessage(
            role="assistant",
            content=_with_disclaimer(text),
            scope_flag=Scope.ALLOWED,
            routed=False,
            sources=sources,
            context_item_names=item_names,
        )

    @staticmethod
    def _select_items(question: str, latest_analysis: Mapping[str, Any]) -> list[dict[str, Any]]:
        """질문 언급 항목 우선, 없으면 주의·이상·응급 및 추적 항목 사용"""
        items = list(latest_analysis.get("items_json") or [])
        q = (question or "").lower()
        mentioned = [
            item for item in items
            if str(item.get("name") or "").lower() in q
        ]
        if mentioned:
            return mentioned[:5]

        tracking = set(latest_analysis.get("tracking_items") or [])
        flagged = [
            item for item in items
            if item.get("status") in _FLAGGED_STATUS or item.get("name") in tracking
        ]
        return flagged[:5]

    def _build_user_prompt(
        self,
        question: str,
        items: list[dict[str, Any]],
    ) -> tuple[str, list[str], list[str]]:
        """검진 항목·해설 dict·카테고리 가이드를 답변 컨텍스트로 압축"""
        lines = [
            f"[사용자 질문] {question}",
            "[검진 항목]",
        ]
        sources: list[str] = []
        item_names: list[str] = []

        for item in items:
            name = str(item.get("name") or "")
            item_names.append(name)
            value_text = item.get("value_text") or item.get("value") or "-"
            unit = item.get("unit") or ""
            status = item.get("status") or ""
            explain = item.get("explain") or ""
            item_source = item.get("source") or ""
            if item_source:
                sources.append(str(item_source))

            lines.append(f"- {name}: {value_text} {unit} / 상태 {status}")
            if explain:
                lines.append(f"  - 기존 해설: {explain}")

            grounding = self._retriever.retrieve(name)
            if grounding:
                lines.append(f"  - 해설 근거: {grounding.get('explanation')}")
                lines.append(f"  - 주의사항: {grounding.get('caution')}")
                if grounding.get("source"):
                    lines.append(f"  - 해설 출처: {grounding.get('source')}")
                    sources.append(str(grounding.get("source")))

            category = category_guide.category_of(name)
            guide = category_guide.guide_for(category) if category else None
            if category and guide:
                lines.append(f"  - 카테고리: {category}")
                lines.append(f"  - 생활 가이드: {guide['lifestyle']}")
                lines.append(f"  - 추적 권장: {guide['tracking']}")
                lines.append(f"  - 상담 진료과: {guide['department']}")
                lines.append(f"  - 생활 가이드 출처: {guide['source']}")
                sources.append(str(guide["source"]))

        lines.append("위 검진 항목과 근거 안에서만 답변하라. 진단·처방·약물 용량 판단은 하지 말라.")
        return "\n".join(lines), _dedupe(sources), item_names
