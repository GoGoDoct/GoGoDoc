"""DictRetriever 어댑터 테스트 - ReferenceRetrieverPort 기본 구현"""

from gogodoc.infrastructure.retrieval.dict_retriever import DictRetriever


def test_dict_retriever_hit():
    # 등록 항목 - 해설 근거 엔트리 반환
    entry = DictRetriever().retrieve("ALT")
    assert entry is not None
    assert "explanation" in entry and "source" in entry


def test_dict_retriever_miss():
    # 미등록 항목 - None
    assert DictRetriever().retrieve("없는항목xyz") is None
