"""컴포지션 루트 조립 테스트."""

from gogodoc.domain.models import ChatMessage, Scope
from gogodoc.infrastructure.config import Settings


def _settings() -> Settings:
    return Settings(
        openai_api_key="test",
        parse_model="gpt-test",
        interpret_model="gpt-test",
        render_dpi=150,
        db_host="localhost",
        db_port=5432,
        db_name="gogodoc",
        db_user="gogodoc",
        db_password="test",
        retriever="dict",
        database_url="",
        embed_model="embed-test",
        retriever_threshold=0.45,
        hira_api_key="",
    )


def test_build_chat_ui_contract_wires_latest_reader_and_answer_service(monkeypatch):
    import gogodoc.composition as composition
    import gogodoc.infrastructure.db.analysis_repository as analysis_repository

    class _FakeAnswerService:
        def route(self, question):
            return None

        def answer_allowed(self, question, latest_analysis, profile=None):
            return ChatMessage(
                role="assistant",
                content=f"{question}:{latest_analysis['filename']}",
                scope_flag=Scope.ALLOWED,
            )

    def fake_find_latest(conn, user_id):
        assert conn == "conn"
        assert user_id == 3
        return {"id": 9, "filename": "latest.pdf", "items_json": []}

    monkeypatch.setattr(
        composition,
        "build_chat_answer_service",
        lambda settings=None: _FakeAnswerService(),
    )
    monkeypatch.setattr(analysis_repository, "find_latest", fake_find_latest)

    contract = composition.build_chat_ui_contract(_settings())
    payload = contract.answer_latest(conn="conn", user_id=3, question="BMI 설명해줘")

    assert payload["content"] == "BMI 설명해줘:latest.pdf"
    assert payload["has_latest_analysis"] is True
    assert payload["analysis_id"] == 9
