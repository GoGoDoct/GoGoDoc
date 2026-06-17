"""F-007 챗봇 스코프 규칙 단위 테스트 - 하드 차단 패턴 (순수 도메인)"""

from gogodoc.domain import chat_scope
from gogodoc.domain.models import QuestionType, Scope


def test_blocks_prescription_and_medication():
    # 처방·복약 질문 하드 차단
    for q in ["무슨 약을 먹어야 하나요?", "혈압약 복용해도 되나요?", "메트포민 용량 얼마예요?",
              "콜레스테롤 약 처방해줘", "지금 먹는 약 끊어도 되나요?"]:
        assert chat_scope.classify_rule(q) == Scope.BLOCKED, q


def test_blocks_diagnosis_and_procedure():
    # 진단 단정·의료행위 하드 차단
    for q in ["저 당뇨병인가요?", "이거 암이에요?", "제 병명이 뭔가요?",
              "수술을 받아야 하나요?", "항암치료 시작해야 하나요?"]:
        assert chat_scope.classify_rule(q) == Scope.BLOCKED, q


def test_allowed_questions_not_hard_blocked():
    # 허용 질문은 규칙에서 차단 안 됨 (None -> LLM 위임)
    for q in ["ALT가 60인데 무슨 의미예요?", "콜레스테롤 낮추려면 어떤 음식이 좋아요?",
              "혈압 관리에 좋은 운동 알려줘", "어느 진료과를 가야 하나요?"]:
        assert chat_scope.classify_rule(q) is None, q


def test_rule_routes_emergency_symptoms_before_llm():
    # 응급 가능 증상은 답변 생성 전에 즉시 라우팅
    for q in ["가슴이 답답하고 숨이 차요", "한쪽 팔에 힘이 안 들어가고 말이 어눌해요", "갑자기 의식을 잃었어요"]:
        d = chat_scope.classify_rule_detail(q)
        assert d is not None
        assert d.scope == Scope.BLOCKED
        assert d.question_type == QuestionType.EMERGENCY_SYMPTOM


def test_rule_routes_self_harm_crisis_before_llm():
    # 자해·자살 위기 표현은 별도 위기 안내로 라우팅
    d = chat_scope.classify_rule_detail("죽고 싶어요")
    assert d is not None
    assert d.scope == Scope.BLOCKED
    assert d.question_type == QuestionType.SELF_HARM_CRISIS


def test_rule_routes_general_symptom_and_nonmedical_out_of_scope():
    # 일반 증상과 비의료 질문은 서로 다른 유형으로 라우팅
    symptom = chat_scope.classify_rule_detail("나 지금 허리가 아픈데")
    out_of_scope = chat_scope.classify_rule_detail("나 지금 배고파")

    assert symptom is not None
    assert symptom.scope == Scope.BLOCKED
    assert symptom.question_type == QuestionType.SYMPTOM_NON_EMERGENCY
    assert out_of_scope is not None
    assert out_of_scope.scope == Scope.BLOCKED
    assert out_of_scope.question_type == QuestionType.OUT_OF_SCOPE_NONMEDICAL


def test_empty_question_blocked():
    # 빈 질문은 보수적으로 차단
    assert chat_scope.classify_rule("") == Scope.BLOCKED
    assert chat_scope.classify_rule("   ") == Scope.BLOCKED
    assert chat_scope.classify_rule_detail("").question_type == QuestionType.UNKNOWN
