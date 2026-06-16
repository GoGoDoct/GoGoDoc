"""생성 평가 회귀 - 가짜 LLM 주입으로 규칙 채점·심판 파싱 검증 (라이브 API 미사용)"""

import json

from evaluation import gen_eval


class FakeLLM:
    """task별 고정 응답 - 생성은 answer, 심판은 verdict JSON"""

    def __init__(self, answer: str, verdict: dict):
        self._answer = answer
        self._verdict = json.dumps(verdict)

    def complete(self, system, user, task):
        return self._verdict if task.value == "judge" else self._answer


CASES = [json.loads(l) for l in gen_eval.GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]


def test_build_grounding_covers_all_types():
    # 수치·정성 소견·복합검사 모두 근거 구성 가능
    numeric = next(c for c in CASES if c["lab_item"] == "공복혈당")
    finding = next(c for c in CASES if c["lab_item"] == "복부초음파")
    comp = next(c for c in CASES if c["lab_item"] == "복합검사")
    for c in (numeric, finding, comp):
        assert gen_eval.build_grounding(c) is not None


def test_keyword_and_forbidden_scoring():
    case = next(c for c in CASES if c["forbidden_keywords"])
    answer = "정상 범위입니다. " + case["forbidden_keywords"][0]  # 금지어 일부러 포함
    llm = FakeLLM(answer, {"groundedness": 1, "major_hallucination": False})
    res = gen_eval.evaluate([case], llm)
    assert res["forbidden_violation"] == 1
    assert res["groundedness"] == 1.0
    assert res["major_hallucination_rate"] == 0.0


def test_verdict_parse_fallback_is_conservative():
    # 심판 JSON 파싱 실패 시 근거성 0·환각 True 보수 처리
    bad = gen_eval._parse_verdict("판정 불가")
    assert bad["groundedness"] == 0.0 and bad["major_hallucination"] is True
    good = gen_eval._parse_verdict('앞말 {"groundedness": 0.5, "major_hallucination": false} 뒷말')
    assert good["groundedness"] == 0.5 and good["major_hallucination"] is False


def test_emergency_urgency_miss_detected():
    emerg = next(c for c in CASES if c["emergency"] == "Y")
    # 응급인데 긴급 톤(즉시·내원) 없는 답변
    llm = FakeLLM("천천히 추적 관찰하세요.", {"groundedness": 1, "major_hallucination": False})
    res = gen_eval.evaluate([emerg], llm)
    assert res["emergency_urgency_miss"] == 1


def test_sample_includes_all_emergencies():
    picked = gen_eval.sample(CASES, limit=10)
    emerg_all = [c for c in CASES if c["emergency"] == "Y" and gen_eval.build_grounding(c)]
    picked_ids = {c["test_id"] for c in picked}
    assert all(c["test_id"] in picked_ids for c in emerg_all)
