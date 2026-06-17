"""변형 구제 평가 회귀 - 정확/오구제 분류·OOV·폴백 임계값 (가짜 retriever, DB 불필요)"""

import json

from evaluation import variant_eval
from gogodoc.domain.services.normalization import canonicalize
from gogodoc.domain.reference import reference_dict
from gogodoc.infrastructure.config import load_settings

CASES = [
    json.loads(l)
    for l in variant_eval.GOLDEN.read_text(encoding="utf-8").splitlines()
    if l.strip()
]


class _FakeRetriever:
    """canon → entry 고정 매핑 (벡터 구제 흉내)"""

    def __init__(self, by_canon):
        self._by = by_canon

    def retrieve(self, query):
        return self._by.get(query)


def _canon(raw):
    c, _, _ = canonicalize(raw)
    return c


def test_golden_loaded():
    assert len(CASES) == 51
    assert sum(c["oov"] for c in CASES) == 8


def test_subject_mapping_roundtrip():
    # 표준명 카드 해설 → 표준명 역매핑
    assert variant_eval._subject_of(reference_dict.lookup("공복혈당")) == "공복혈당"
    assert variant_eval._subject_of(None) is None


def test_correct_vs_wrong_rescue_classification():
    glu = next(c for c in CASES if c["raw_name"] == "공복 혈당 수치")  # 기대 공복혈당
    liver = next(c for c in CASES if c["raw_name"] == "간 기능 검사")  # 기대 AST/ALT/감마
    # 정확 구제: 공복혈당 카드 반환 / 오구제: 엉뚱한 TSH 카드 반환
    fake = _FakeRetriever({
        _canon("공복 혈당 수치"): reference_dict.lookup("공복혈당"),
        _canon("간 기능 검사"): reference_dict.lookup("TSH"),
    })
    m = variant_eval.evaluate([glu, liver], fake)
    assert m["correct_rescue"] == 1
    assert m["wrong_rescue"] == 1
    assert m["rescue_precision"] == 0.5


def test_oov_blocked_when_retriever_returns_none():
    oov = [c for c in CASES if c["oov"]]
    m = variant_eval.evaluate(oov, _FakeRetriever({}))
    assert m["oov_block"] == m["oov_total"] == 8


def test_fallback_threshold_default_is_conservative():
    # 폴백 전용 임계값 0.50 - 본 임계값(0.55)보다 보수적(오구제 차단)
    s = load_settings()
    assert s.hybrid_fallback_threshold == 0.50
    assert s.hybrid_fallback_threshold < s.retriever_threshold
