"""PgvectorRetriever 테스트 - 임계값·폴백 (실 DB 불필요, 커넥션 주입으로 검증)"""

from gogodoc.infrastructure.retrieval.pgvector_retriever import PgvectorRetriever
from gogodoc.domain.reference import reference_dict


class _BadEmbedder:
    """임베딩 실패 주입 - retrieve 가 폴백 경로를 타도록"""

    def embed(self, text: str) -> list[float]:
        raise RuntimeError("임베딩 불가")


class _OkEmbedder:
    """정상 임베딩 주입 - 값은 무의미 (가짜 커넥션이 거리 결정)"""

    def embed(self, text: str) -> list[float]:
        return [0.0, 0.0, 0.0]


class _FakeConn:
    """가짜 pgvector 커넥션 - 고정된 (entry, dist) row 반환"""

    def __init__(self, row):
        self._row = row

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def execute(self, sql, params):
        self._last = self._row
        return self

    def fetchone(self):
        return self._last


def _connect_returning(row):
    """row 를 돌려주는 가짜 connect 팩토리"""

    def _connect(dsn, **kw):
        return _FakeConn(row)

    return _connect


# ── 폴백 (예외) ────────────────────────────────────────────────────────
def test_falls_back_to_dict_on_failure():
    # 임베딩/DB 실패(예외) 시 dict 키 조회로 폴백
    r = PgvectorRetriever("postgresql://invalid", _BadEmbedder())
    entry = r.retrieve("ALT")
    assert entry is not None and "explanation" in entry


def test_fallback_miss_returns_none():
    # 폴백에서도 미등록 항목은 None
    r = PgvectorRetriever("postgresql://invalid", _BadEmbedder())
    assert r.retrieve("없는항목xyz") is None


# ── 임계값 (벡터 검색 성공) ──────────────────────────────────────────────
def test_near_match_returns_entry():
    # 임계값 이내 최근접 - 엔트리 반환
    alt = reference_dict.lookup("ALT")
    r = PgvectorRetriever(
        "postgresql://x", _OkEmbedder(), threshold=0.45, connect=_connect_returning((alt, 0.1))
    )
    assert r.retrieve("ALT") == alt


def test_far_match_rejected_as_oov():
    # 임계값 초과 최근접 - dict 에 있어도 None (OOV 오적중 차단, 폴백하지 않음)
    alt = reference_dict.lookup("ALT")
    r = PgvectorRetriever(
        "postgresql://x", _OkEmbedder(), threshold=0.45, connect=_connect_returning((alt, 0.9))
    )
    assert r.retrieve("백혈구") is None


def test_empty_index_falls_back():
    # 색인 비어있음(row=None) - dict 폴백
    r = PgvectorRetriever(
        "postgresql://x", _OkEmbedder(), threshold=0.45, connect=_connect_returning(None)
    )
    assert r.retrieve("ALT") is not None
    assert r.retrieve("없는항목xyz") is None
