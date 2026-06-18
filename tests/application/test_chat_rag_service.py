"""F-007 ChatRagService 테스트 - 검색·근거 답변 (가짜 LLM, API 불필요)"""

from gogodoc.application.chat_rag_service import ChatRagService, _match_items, _match_categories
from gogodoc.application.ports import LLMTask
from gogodoc.domain.models import (
    FinalReport, InterpretedItem, UserProfile, Sex, Flag, Scope,
)


class _EchoLLM:
    """주입된 user 프롬프트를 그대로 반환하는 가짜 LLM (근거 주입 검증용)"""

    def complete(self, system, user, task: LLMTask) -> str:
        assert task == LLMTask.INTERPRET
        return "근거 기반 답변입니다. 출처: 질병관리청. 참고용입니다."


class _BoomLLM:
    def complete(self, system, user, task):
        raise RuntimeError("LLM 실패")


def _report():
    return FinalReport(items=[
        InterpretedItem(canonical_name="ALT", raw_name="ALT", value=60, unit="U/L",
                        flag=Flag.CAUTION, explanation="간 효소"),
    ])


def _profile():
    return UserProfile(sex=Sex.MALE, age=45)


def test_match_items_detects_checkup_terms():
    assert _match_items("ALT가 60인데 괜찮아요?") == ["ALT"]
    assert _match_items("혈색소 수치가 뭘 의미해요?") == ["헤모글로빈"]
    assert _match_items("당화혈색소 5.8이면 괜찮나요?") == ["당화혈색소"]
    assert _match_items("BMI랑 요산도 봐줘") == ["BMI", "요산"]
    assert _match_items("오늘 날씨 어때?") == []


def test_match_items_accepts_compact_item_variants():
    assert _match_items("내 감마 지티피 어때") == ["감마지티피"]
    assert _match_items("gamma gtp 수치 어때") == ["감마지티피"]
    assert _match_items("LDL 콜레스테롤 수치 어때") == ["LDL 콜레스테롤"]


def test_match_items_does_not_match_gamma_like_unrelated_terms():
    assert _match_items("감마선이 뭐야") == []
    assert _match_items("지피티가 뭐야") == []
    assert _match_items("감기 때문에 힘들어") == []


def test_match_categories_generic_terms():
    # 특정 항목명 없이도 포괄 키워드로 카테고리 매칭
    assert "지질" in _match_categories("콜레스테롤 낮추려면 뭐 먹어요?", [])
    assert "혈압" in _match_categories("혈압 관리 운동 알려줘", [])


def test_answer_grounds_and_cites():
    svc = ChatRagService(_EchoLLM())
    msg = svc.answer("ALT가 60인데 괜찮아요?", report=_report(), profile=_profile())
    assert msg.role == "assistant"
    assert msg.scope_flag == Scope.ALLOWED
    assert "ALT" in msg.context_item_names
    assert any("질병관리청" in s or "간기능" in s for s in msg.sources)  # 출처 채워짐


def test_answer_no_grounding_routes_to_consult():
    svc = ChatRagService(_EchoLLM())
    msg = svc.answer("오늘 기분이 어때?", report=None, profile=None)
    assert msg.context_item_names == [] and msg.sources == []
    assert "전문의" in msg.content or "참고용" in msg.content


def test_answer_llm_failure_fallback():
    svc = ChatRagService(_BoomLLM())
    msg = svc.answer("ALT가 뭐예요?", report=_report(), profile=_profile())
    assert "참고용" in msg.content  # 폴백 메시지
    assert msg.scope_flag == Scope.ALLOWED
