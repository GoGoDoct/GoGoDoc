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


def test_qualitative_findings_are_counted_as_supported_cases():
    cases = [
        ("RAG-062", "요단백", "음성", "정상"),
        ("RAG-063", "요단백", "약양성(±)", "주의"),
        ("RAG-064", "요단백", "양성(2+)", "이상"),
        ("RAG-084", "위내시경", "만성위염", "주의"),
        ("RAG-085", "위내시경", "위궤양", "이상"),
        ("RAG-086", "대장내시경", "대장용종", "이상"),
        ("RAG-087", "복부초음파", "지방간", "주의"),
        ("RAG-088", "복부초음파", "담낭용종", "주의"),
        ("RAG-089", "B형간염 표면항원", "양성", "이상"),
    ]

    result = evaluate([
        {
            "test_id": test_id,
            "lab_item": lab_item,
            "value": value,
            "risk_level": risk_level,
            "emergency": "N",
        }
        for test_id, lab_item, value, risk_level in cases
    ])

    rows = {row["id"]: row for row in result["rows"]}
    for test_id, _, _, risk_level in cases:
        assert rows[test_id]["supported"] is True
        assert rows[test_id]["pred"] == risk_level
    assert result["coverage"] == 1.0
    assert result["clinical_correctness"] == 1.0
