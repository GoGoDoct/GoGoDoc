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


def test_unsupported_counted_not_hidden():
    # 비수치 소견·복합검사 12건은 미지원으로 노출 (조용히 통과 금지)
    result = retrieval_eval.evaluate(CASES, DictRetriever())
    unsup = [r for r in result["rows"] if not r["supported"]]
    assert len(unsup) == 12
    assert result["metrics"]["coverage"] == 0.88


def test_synonym_resolution_hits():
    # SGOT->AST, HbA1c->당화혈색소, 혈색소->헤모글로빈 동의어 해소 적중
    syn = [c for c in CASES if c["lab_item"] in ("SGOT", "SGPT", "HbA1c", "혈색소")]
    result = retrieval_eval.evaluate(syn, DictRetriever())
    assert result["metrics"]["recall_at_3"] == 1.0
