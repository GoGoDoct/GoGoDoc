"""HybridRetriever 테스트 - dict 우선·벡터 폴백·OOV 차단 (실 DB 불필요)"""

from gogodoc.infrastructure.retrieval.hybrid_retriever import HybridRetriever


class _Stub:
    """고정 응답 리트리버 - 호출 여부 기록"""

    def __init__(self, result):
        self._result = result
        self.called = False

    def retrieve(self, query):
        self.called = True
        return self._result


def test_dict_hit_short_circuits_fallback():
    # dict 적중 - 벡터 폴백 호출 안 함(무지연·정확)
    primary = _Stub({"explanation": "정확매칭"})
    fallback = _Stub({"explanation": "벡터"})
    hyb = HybridRetriever(primary, fallback)
    assert hyb.retrieve("ALT")["explanation"] == "정확매칭"
    assert not fallback.called


def test_dict_miss_falls_back_to_vector():
    # dict 미적중(변형명) - 벡터 의미검색으로 구제
    primary = _Stub(None)
    fallback = _Stub({"explanation": "벡터 구제"})
    hyb = HybridRetriever(primary, fallback)
    assert hyb.retrieve("공복 혈당 수치")["explanation"] == "벡터 구제"
    assert fallback.called


def test_both_miss_returns_none():
    # dict·벡터 모두 미적중(진짜 OOV) - None (OOV 차단 유지)
    hyb = HybridRetriever(_Stub(None), _Stub(None))
    assert hyb.retrieve("아스파라거스") is None
