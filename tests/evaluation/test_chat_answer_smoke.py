"""F-007 챗봇 답변 스모크 CLI 테스트."""

import json

from evaluation.chat_answer_smoke import NoAnalysisError, main, run_smoke


def _latest_analysis() -> dict:
    return {
        "tracking_items": ["BMI"],
        "emergency_alerts": [],
        "items_json": [
            {
                "name": "BMI",
                "value": 27.1,
                "value_text": "27.1",
                "unit": "kg/m2",
                "status": "이상",
                "explain": "키 대비 체중으로 비만 정도를 보는 체질량지수입니다.",
                "source": "대한비만학회 비만 진료지침",
            }
        ],
    }


def test_fake_mode_allowed_question_reports_context_and_answer_llm_call():
    result = run_smoke(
        question="BMI가 높으면 어떻게 관리해요?",
        latest_analysis=_latest_analysis(),
        mode="fake",
    )

    assert result["scope_flag"] == "allowed"
    assert result["routed"] is False
    assert result["context_item_names"] == ["BMI"]
    assert any("대한비만학회" in source for source in result["sources"])
    assert result["answer_llm_called"] is True
    assert "스모크" in result["answer_preview"]


def test_fake_mode_blocked_question_does_not_call_answer_llm():
    result = run_smoke(
        question="무슨 약을 먹어야 하나요?",
        latest_analysis=_latest_analysis(),
        mode="fake",
    )

    assert result["scope_flag"] == "blocked"
    assert result["routed"] is True
    assert result["answer_llm_called"] is False
    assert result["context_item_names"] == []


def test_run_smoke_raises_when_latest_analysis_is_missing():
    try:
        run_smoke(question="ALT가 무슨 뜻이에요?", latest_analysis=None, mode="fake")
    except NoAnalysisError as exc:
        assert "analysis_results 없음" in str(exc)
    else:
        raise AssertionError("NoAnalysisError가 발생해야 합니다")


def test_main_returns_exit_2_when_latest_analysis_is_missing(capsys):
    exit_code = main(
        ["--user-id", "999", "--question", "ALT가 무슨 뜻이에요?"],
        latest_loader=lambda _user_id: None,
    )

    captured = capsys.readouterr()
    assert exit_code == 2
    assert "analysis_results 없음" in captured.err


def test_main_prints_json_smoke_result(capsys):
    exit_code = main(
        ["--user-id", "1", "--question", "BMI가 높으면 어떻게 관리해요?"],
        latest_loader=lambda _user_id: _latest_analysis(),
    )

    captured = capsys.readouterr()
    payload = json.loads(captured.out)
    assert exit_code == 0
    assert payload["scope_flag"] == "allowed"
    assert payload["routed"] is False
    assert "sources" in payload
