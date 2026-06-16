"""F-007 Streamlit 챗봇 패널 상태 헬퍼 테스트."""

from gogodoc.application.chat_ui_session import (
    append_chat_exchange,
    is_test_ui_enabled,
    profile_from_session,
    submit_latest_question,
)
from gogodoc.domain.models import Sex


class _FakeContract:
    def __init__(self):
        self.calls = []

    def answer_latest(self, *, conn, user_id, question, profile=None):
        self.calls.append({
            "conn": conn,
            "user_id": user_id,
            "question": question,
            "profile": profile,
        })
        return {
            "content": "BMI 답변",
            "scope_flag": "allowed",
            "routed": False,
            "sources": ["대한비만학회"],
            "context_item_names": ["BMI"],
            "latest_analysis_checked": True,
            "has_latest_analysis": True,
            "analysis_id": 3,
            "analysis_filename": "latest.pdf",
        }


def test_test_ui_enabled_is_opt_in_only():
    assert is_test_ui_enabled(None) is False
    assert is_test_ui_enabled("") is False
    assert is_test_ui_enabled("0") is False
    assert is_test_ui_enabled("1") is True
    assert is_test_ui_enabled("true") is True
    assert is_test_ui_enabled("ON") is True


def test_profile_from_session_uses_streamlit_sex_and_age_values():
    profile = profile_from_session("female", "37")

    assert profile.sex == Sex.FEMALE
    assert profile.age == 37


def test_submit_latest_question_calls_contract_and_releases_connection():
    contract = _FakeContract()
    released = []

    payload = submit_latest_question(
        contract=contract,
        pool="pool",
        user_id=7,
        question=" BMI가 높으면 어떻게 관리해요? ",
        profile=profile_from_session("male", 45),
        get_conn_fn=lambda pool: "conn",
        put_conn_fn=lambda pool, conn: released.append((pool, conn)),
    )

    assert payload["content"] == "BMI 답변"
    assert contract.calls[0]["conn"] == "conn"
    assert contract.calls[0]["user_id"] == 7
    assert contract.calls[0]["question"] == "BMI가 높으면 어떻게 관리해요?"
    assert contract.calls[0]["profile"].sex == Sex.MALE
    assert released == [("pool", "conn")]


def test_submit_latest_question_ignores_blank_question():
    contract = _FakeContract()

    payload = submit_latest_question(
        contract=contract,
        pool="pool",
        user_id=7,
        question="  ",
        profile=None,
        get_conn_fn=lambda pool: "conn",
        put_conn_fn=lambda pool, conn: None,
    )

    assert payload is None
    assert contract.calls == []


def test_append_chat_exchange_adds_user_and_assistant_messages():
    history = [{"role": "assistant", "content": "이전 답변"}]
    payload = {
        "content": "BMI 답변",
        "scope_flag": "allowed",
        "routed": False,
        "sources": ["대한비만학회"],
        "context_item_names": ["BMI"],
        "latest_analysis_checked": True,
        "has_latest_analysis": True,
        "analysis_id": 3,
        "analysis_filename": "latest.pdf",
    }

    updated = append_chat_exchange(history, "BMI 질문", payload)

    assert updated is not history
    assert [msg["role"] for msg in updated] == ["assistant", "user", "assistant"]
    assert updated[-2]["content"] == "BMI 질문"
    assert updated[-1]["content"] == "BMI 답변"
    assert updated[-1]["payload"] == payload
