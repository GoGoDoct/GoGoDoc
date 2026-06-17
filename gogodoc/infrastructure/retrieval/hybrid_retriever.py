"""하이브리드 근거 검색 어댑터 - dict 정확매칭 우선 + pgvector 의미검색 폴백

운영 파이프라인은 동의어 정규화를 먼저 하므로 표준명 정확매칭(dict)이 무지연·정확하다.
dict 가 잡으면 그대로 반환(알려진 항목 100% 유지). dict miss(동의어 사전 미등록 변형·미수록)는
pgvector 임베딩 의미검색으로 구제하되, 벡터 임계값이 OOV 오적중을 여전히 차단한다.

실측 근거(RAG_METRICS.md §7): 정규화 후 dict 정답률 100% vs pgvector 단독 71% - 통째 전환은
회귀. 하이브리드는 100% 유지 + 사전이 못 잡는 변형·OOV 를 벡터로 의미 해소.
"""


class HybridRetriever:
    """dict 정확매칭 우선, miss 시 pgvector 의미검색 폴백"""

    def __init__(self, primary, fallback) -> None:
        self._primary = primary  # DictRetriever - 정확·무지연
        self._fallback = fallback  # PgvectorRetriever - 의미검색(임계값 OOV 차단)

    def retrieve(self, query: str) -> dict | None:
        """표준명 정확매칭 우선 - 미적중 시 벡터 의미검색 (둘 다 미스면 None)"""
        hit = self._primary.retrieve(query)
        if hit is not None:
            return hit
        return self._fallback.retrieve(query)
