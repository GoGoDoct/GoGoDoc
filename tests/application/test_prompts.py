"""해석 프롬프트·RAG 근거 고정 테스트 (F-004)

근거 dict 가 프롬프트에 주입되는지(RAG grounding)와 가드레일 제약을 검증
"""

from gogodoc.application import prompts
from gogodoc.application.prompts import INTERPRET_SYSTEM, STRUCTURING_SYSTEM
from gogodoc.domain.models import MatchedItem, UserProfile, Sex, Flag

_GROUNDING = {
    "explanation": "간세포 손상 시 올라가는 효소",
    "caution": "40 초과 시 추적 관찰 권장",
    "source": "질병관리청 국가건강정보포털",
}


def _item():
    return MatchedItem(
        canonical_name="ALT", raw_name="ALT", value=52, unit="U/L",
        flag=Flag.CAUTION, matched=True,
    )


def _profile():
    return UserProfile(sex=Sex.MALE, age=40)


def test_user_prompt_injects_grounding():
    # RAG - 검색한 근거(해설·주의·출처·범위)가 프롬프트에 주입됨
    text = prompts.build_interpret_user(_item(), _profile(), _GROUNDING, (0, 40))
    for token in ["ALT", "52", "간세포 손상", "추적 관찰", "질병관리청", "(0, 40)"]:
        assert token in text, f"근거 누락: {token}"
    assert "위 근거만 사용" in text


def test_system_prompt_constraints():
    # 근거 고정·단정 금지·3-5문장 제약
    assert "근거" in INTERPRET_SYSTEM
    assert "3-5문장" in INTERPRET_SYSTEM
    assert "병이다" in INTERPRET_SYSTEM  # 단정 표현 금지 지시 (가드레일)
    assert "근거에 없는" in INTERPRET_SYSTEM  # 근거 밖 추론 차단


def test_structuring_prompt_is_json():
    # 파싱 프롬프트는 JSON 구조화 지시
    assert "JSON" in STRUCTURING_SYSTEM
