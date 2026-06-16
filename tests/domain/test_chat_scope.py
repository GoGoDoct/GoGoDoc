"""F-007 챗봇 스코프 규칙 단위 테스트 - 하드 차단 패턴 (순수 도메인)"""

from gogodoc.domain import chat_scope
from gogodoc.domain.models import Scope


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


def test_empty_question_blocked():
    # 빈 질문은 보수적으로 차단
    assert chat_scope.classify_rule("") == Scope.BLOCKED
    assert chat_scope.classify_rule("   ") == Scope.BLOCKED
