"""팀 골든 검색 평가 회귀 - 수록 적중·미지원 집계·금지 항목 회피"""

import json
from pathlib import Path

from evaluation import retrieval_eval
from gogodoc.infrastructure.retrieval.dict_retriever import DictRetriever

CASES = [
    json.loads(l)
    for l in retrieval_eval.TEAM_GOLDEN.read_text(encoding="utf-8").splitlines()
    if l.strip()
]


def test_team_golden_loaded():
    assert len(CASES) == 100


def test_supported_recall_and_negative():
    result = retrieval_eval.evaluate(CASES, DictRetriever())
    m = result["metrics"]
    # 수록 항목은 모두 정답 카드 적중, 금지 항목 회피 완전
    assert m["recall_at_3"] == 1.0
    assert m["precision_at_3"] == 1.0
    assert m["negative_retrieval_rate"] == 1.0
    assert m["k_effective"] == 1


def test_full_coverage_after_kb_expansion():
    # 정성 소견 KB + 복합검사 분해 도입으로 전 항목 시스템 지원
    result = retrieval_eval.evaluate(CASES, DictRetriever())
    unsup = [r for r in result["rows"] if not r["supported"]]
    assert len(unsup) == 0
    assert result["metrics"]["coverage"] == 1.0


def test_qualitative_and_composite_supported():
    # 비수치 소견·복합검사가 미지원이 아닌 적중으로 채점
    qual = [c for c in CASES if c["lab_item"] in ("요단백", "위내시경", "복부초음파")]
    comp = [c for c in CASES if c["lab_item"] == "복합검사"]
    for subset in (qual, comp):
        r = retrieval_eval.evaluate(subset, DictRetriever())["metrics"]
        assert r["coverage"] == 1.0
        assert r["recall_at_3"] == 1.0


def test_synonym_resolution_hits():
    # SGOT->AST, HbA1c->당화혈색소, 혈색소->헤모글로빈 동의어 해소 적중
    syn = [c for c in CASES if c["lab_item"] in ("SGOT", "SGPT", "HbA1c", "혈색소")]
    result = retrieval_eval.evaluate(syn, DictRetriever())
    assert result["metrics"]["recall_at_3"] == 1.0
