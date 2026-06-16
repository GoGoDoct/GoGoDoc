"""pgvector 근거 검색 어댑터 - ReferenceRetrieverPort 벡터 구현

질의(원본 항목명 가능) 임베딩 → pgvector 코사인 유사도 검색 → 해설 근거 엔트리 반환

안전 규칙
- 유사도 임계값(threshold) 초과(= 너무 먼 최근접) 시 None 반환 - 미수록(OOV) 항목 오적중 차단
- DB·임베딩·연결 실패(예외) 시에만 dict 폴백 - 의료 서비스 가용성 안전망
  (먼 매칭은 "근거 없음"이 정답이므로 폴백하지 않고 None)
"""

import psycopg

from gogodoc.infrastructure.retrieval.dict_retriever import DictRetriever
from gogodoc.infrastructure.retrieval.embedder import OpenAIEmbedder

# 색인 테이블
TABLE = "reference_chunks"

# 코사인 거리(<=>) 기본 임계값 - 0(동일)~2(반대), 초과 시 미수록 처리. 실측으로 튜닝
DEFAULT_THRESHOLD = 0.45


def vector_literal(vector: list[float]) -> str:
    """임베딩 벡터를 pgvector 리터럴 문자열로 변환 - %s::vector 캐스트용"""
    return "[" + ",".join(repr(x) for x in vector) + "]"


class PgvectorRetriever:
    """pgvector 유사도 검색 기반 근거 검색 (임계값 OOV 차단 + dict 비상 폴백)"""

    def __init__(
        self,
        dsn: str,
        embedder: OpenAIEmbedder,
        fallback=None,
        threshold: float = DEFAULT_THRESHOLD,
        connect=psycopg.connect,
    ) -> None:
        self._dsn = dsn
        self._embedder = embedder
        self._fallback = fallback or DictRetriever()
        self._threshold = threshold
        self._connect = connect  # 주입 가능 - 테스트에서 가짜 커넥션 사용

    def retrieve(self, query: str) -> dict | None:
        """질의 최근접 근거 엔트리 반환 - 임계값 초과 None, 장애 시 dict 폴백

        query 는 원본 항목명도 허용 (임베딩이 변형명을 의미로 해소)
        """
        try:
            vector = self._embedder.embed(query)
            with self._connect(self._dsn, connect_timeout=3) as conn:
                row = conn.execute(
                    f"SELECT entry, embedding <=> %s::vector AS dist "
                    f"FROM {TABLE} ORDER BY dist LIMIT 1",
                    (vector_literal(vector),),
                ).fetchone()
        except Exception:
            # DB·임베딩·연결 실패 - 키 조회로 폴백 (가용성 안전망)
            return self._fallback.retrieve(query)

        # 색인 비어있음 - 폴백
        if row is None:
            return self._fallback.retrieve(query)

        entry, dist = row[0], row[1]
        # 최근접이 임계값 밖 - 미수록(OOV) 항목, 근거 없음이 정답
        if dist is not None and dist > self._threshold:
            return None
        return entry
