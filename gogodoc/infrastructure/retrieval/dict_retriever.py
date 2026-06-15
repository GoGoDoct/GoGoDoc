"""dict 근거 검색 어댑터 - ReferenceRetrieverPort 기본 구현

정적 reference_dict 키 조회 (결정론·무지연). 벡터 DB 미사용 경로의 기본값
"""

from gogodoc.domain.reference import reference_dict


class DictRetriever:
    """표준 항목명 키 조회 기반 근거 검색"""

    def retrieve(self, canonical_name: str) -> dict | None:
        """표준 항목명으로 해설 근거 엔트리 조회"""
        return reference_dict.lookup(canonical_name)
