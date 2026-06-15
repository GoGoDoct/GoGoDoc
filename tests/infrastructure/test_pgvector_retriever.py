"""PgvectorRetriever 폴백 테스트 - DB·임베딩 실패 시 dict 폴백 (DB 불필요)"""

from gogodoc.infrastructure.retrieval.pgvector_retriever import PgvectorRetriever


class _BadEmbedder:
    """임베딩 실패 주입 - retrieve 가 폴백 경로를 타도록"""

    def embed(self, text: str) -> list[float]:
        raise RuntimeError("임베딩 불가")


def test_falls_back_to_dict_on_failure():
    # 임베딩/DB 실패 시 dict 키 조회로 폴백
    r = PgvectorRetriever("postgresql://invalid", _BadEmbedder())
    entry = r.retrieve("ALT")
    assert entry is not None and "explanation" in entry


def test_fallback_miss_returns_none():
    # 폴백에서도 미등록 항목은 None
    r = PgvectorRetriever("postgresql://invalid", _BadEmbedder())
    assert r.retrieve("없는항목xyz") is None
