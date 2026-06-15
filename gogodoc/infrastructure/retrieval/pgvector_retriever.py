"""pgvector 근거 검색 어댑터 - ReferenceRetrieverPort 벡터 구현

질의 임베딩 → pgvector 코사인 유사도 검색 → 해설 근거 엔트리 반환
DB·임베딩 실패 시 dict 폴백 (의료 안전 - 근거 없으면 멈추지 않고 키 조회로 대체)
"""

import psycopg

from gogodoc.infrastructure.retrieval.dict_retriever import DictRetriever
from gogodoc.infrastructure.retrieval.embedder import OpenAIEmbedder

# 색인 테이블
TABLE = "reference_chunks"


def vector_literal(vector: list[float]) -> str:
    """임베딩 벡터를 pgvector 리터럴 문자열로 변환 - %s::vector 캐스트용"""
    return "[" + ",".join(repr(x) for x in vector) + "]"


class PgvectorRetriever:
    """pgvector 유사도 검색 기반 근거 검색 (dict 폴백 내장)"""

    def __init__(self, dsn: str, embedder: OpenAIEmbedder, fallback=None) -> None:
        self._dsn = dsn
        self._embedder = embedder
        self._fallback = fallback or DictRetriever()

    def retrieve(self, canonical_name: str) -> dict | None:
        """벡터 유사도 최상위 근거 엔트리 반환 - 실패 시 dict 폴백"""
        try:
            vector = self._embedder.embed(canonical_name)
            with psycopg.connect(self._dsn, connect_timeout=3) as conn:
                row = conn.execute(
                    f"SELECT entry FROM {TABLE} ORDER BY embedding <=> %s::vector LIMIT 1",
                    (vector_literal(vector),),
                ).fetchone()
            if row:
                return row[0]
        except Exception:
            # DB·임베딩·연결 실패 - 키 조회로 폴백
            pass
        return self._fallback.retrieve(canonical_name)
