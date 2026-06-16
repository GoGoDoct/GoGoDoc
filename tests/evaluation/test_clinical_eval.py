"""팀 골든 임상 평가기 테스트."""

from evaluation.clinical_eval import evaluate


def test_composite_emergency_case_counts_as_supported_emergency():
    result = evaluate([
        {
            "test_id": "RAG-093",
            "lab_item": "복합검사",
            "value": "공복혈당380/혈압200",
            "risk_level": "응급",
            "emergency": "Y",
        }
    ])

    row = result["rows"][0]
    assert row["supported"] is True
    assert row["pred"] == "응급"
    assert row["canon"] == "복합검사"
    assert result["coverage"] == 1.0
    assert result["clinical_correctness"] == 1.0
    assert result["emergency_recall"] == 1.0


def test_composite_cases_use_highest_component_risk():
    result = evaluate([
        {
            "test_id": "RAG-091",
            "lab_item": "복합검사",
            "value": "공복혈당118/ALT70/HDL38",
            "risk_level": "주의",
            "emergency": "N",
        },
        {
            "test_id": "RAG-092",
            "lab_item": "복합검사",
            "value": "혈압150/총콜250/중성지방280",
            "risk_level": "이상",
            "emergency": "N",
        },
    ])

    rows = {row["id"]: row for row in result["rows"]}
    assert rows["RAG-091"]["supported"] is True
    assert rows["RAG-091"]["pred"] == "주의"
    assert rows["RAG-092"]["supported"] is True
    assert rows["RAG-092"]["pred"] == "이상"
    assert result["coverage"] == 1.0
    assert result["clinical_correctness"] == 1.0
