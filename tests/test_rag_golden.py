"""RAG 골든 데이터셋 회귀 테스트

evaluation/ 하니스를 import 해 핵심 케이스가 모두 통과하는지 검증한다
(평가 자산·시계열 기록은 evaluation/ 에 있고, 여기서는 CI 회귀 게이트만 담당)
"""

from evaluation import harness


def _summary():
    return harness.run(kind="dict")


def test_core_cases_all_pass():
    """핵심 회귀 케이스(known_gap 제외)는 전부 통과해야 한다"""
    rows = _summary()["rows"]
    core, _ = harness.split_core_gap(rows)
    fails = [r["id"] for r in core if not r["all_ok"]]
    assert not fails, f"핵심 케이스 실패: {fails}"


def test_no_false_positive_in_core():
    """핵심 케이스에 오적중(엉뚱한 근거 검색)이 없어야 한다 - 의료 안전"""
    rows = _summary()["rows"]
    core, _ = harness.split_core_gap(rows)
    fps = [r["id"] for r in core if r["false_pos"]]
    assert not fps, f"핵심 케이스 오적중: {fps}"


def test_known_gaps_still_failing():
    """known_gap 케이스가 통과하면 해소된 것 - known_gap=false 로 승격 알림"""
    rows = _summary()["rows"]
    _, gap = harness.split_core_gap(rows)
    resolved = [r["id"] for r in gap if r["all_ok"]]
    assert not resolved, f"known_gap 해소됨 - rag_golden.jsonl 에서 known_gap=false 로 승격 권장: {resolved}"
