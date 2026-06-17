"""F-007 ChatAnswerService 통합 정책 평가 테스트."""

from evaluation.chat_answer_service_eval import evaluate


def _case(question: str, expected: dict, *, classifier: dict | None = None) -> dict:
    case = {
        "id": "T001",
        "question": question,
        "latest_analysis": "baseline",
        "expected": expected,
    }
    if classifier is not None:
        case["classifier"] = classifier
    return case


def test_evaluate_blocked_rule_does_not_call_answer_llm():
    result = evaluate([
        _case(
            "무슨 약을 먹어야 하나요?",
            {
                "scope_flag": "blocked",
                "routed": True,
                "question_type": "prescription_request",
                "route_reason": "prescription_rule",
                "answer_llm_call_count": 0,
                "context_item_names": [],
                "sources_contains": [],
                "content_contains": ["약 처방", "본 해석은 참고용"],
                "requires_disclaimer": True,
            },
        )
    ])

    assert result["failed"] == 0


def test_evaluate_allowed_grounded_question_calls_answer_llm_once():
    result = evaluate([
        _case(
            "BMI가 높으면 어떻게 관리해요?",
            {
                "scope_flag": "allowed",
                "routed": False,
                "question_type": "lifestyle_general",
                "route_reason": "rag_answer",
                "answer_llm_call_count": 1,
                "context_item_names": ["BMI"],
                "sources_contains": ["대한비만학회"],
                "content_contains": ["통합 평가용 답변", "본 해석은 참고용"],
                "requires_disclaimer": True,
            },
            classifier={
                "scope": "allowed",
                "question_type": "lifestyle_general",
                "route_reason": "test_lifestyle",
            },
        )
    ])

    assert result["failed"] == 0


def test_evaluate_checkup_summary_does_not_call_answer_llm():
    result = evaluate([
        _case(
            "검진 결과 확인해야 할 항목 알려줘",
            {
                "scope_flag": "allowed",
                "routed": False,
                "question_type": "checkup_summary",
                "route_reason": "summary_answer",
                "answer_llm_call_count": 0,
                "context_item_names": ["BMI", "ALT"],
                "sources_contains": ["대한비만학회", "질병관리청"],
                "content_contains": ["최신 검진 결과", "본 해석은 참고용"],
                "requires_disclaimer": True,
            },
        )
    ])

    assert result["failed"] == 0


def test_evaluate_no_grounding_preserves_question_type_without_answer_llm():
    case = _case(
        "어느 진료과 가야 해요?",
        {
            "scope_flag": "allowed",
            "routed": False,
            "question_type": "department_guide",
            "route_reason": "no_grounding",
            "answer_llm_call_count": 0,
            "context_item_names": [],
            "sources_contains": [],
            "content_contains": ["관련된 항목을 찾지 못했습니다", "본 해석은 참고용"],
            "requires_disclaimer": True,
        },
        classifier={
            "scope": "allowed",
            "question_type": "department_guide",
            "route_reason": "test_department",
        },
    )
    case["latest_analysis"] = "empty"

    result = evaluate([case])

    assert result["failed"] == 0


def test_evaluate_fails_on_answer_llm_call_count_mismatch():
    result = evaluate([
        _case(
            "BMI가 높으면 어떻게 관리해요?",
            {
                "scope_flag": "allowed",
                "routed": False,
                "question_type": "lifestyle_general",
                "route_reason": "rag_answer",
                "answer_llm_call_count": 0,
                "context_item_names": ["BMI"],
                "sources_contains": ["대한비만학회"],
                "content_contains": ["통합 평가용 답변"],
            },
            classifier={
                "scope": "allowed",
                "question_type": "lifestyle_general",
                "route_reason": "test_lifestyle",
            },
        )
    ])

    assert result["failed"] == 1
    assert "answer_llm_call_count" in result["rows"][0]["failures"][0]
