"""해설 dict → pgvector 색인 스크립트

reference_dict 각 항목과 동의어 변형명을 OpenAI 임베딩으로 벡터화하여 pgvector 에 적재
표준명뿐 아니라 변형명(gpt, fbs, hba1c 등)도 각각 색인 → 원본명 벡터 검색이 변형을 해소
실행: python -m scripts.index_reference  (DATABASE_URL·OPENAI_API_KEY 필요)

주의: term 키 스키마로 변경됨 - 구버전(canonical_name UNIQUE) 테이블이 있으면 먼저 DROP 후 재색인
"""

import json

import psycopg

from gogodoc.infrastructure.config import load_settings
from gogodoc.infrastructure.retrieval.embedder import OpenAIEmbedder
from gogodoc.infrastructure.retrieval.pgvector_retriever import TABLE, vector_literal
from gogodoc.domain.reference.reference_dict import REFERENCE
from gogodoc.domain.reference.synonyms import SYNONYMS
from gogodoc.domain.reference.findings import FINDINGS

# text-embedding-3-small 차원
_DIM = 1536


def _terms_by_canonical() -> dict[str, set[str]]:
    """표준명별 색인 대상 표기 집합 - 표준명 자신 + 매핑된 동의어 변형명"""
    terms = {name: {name} for name in REFERENCE}
    for variant, canon in SYNONYMS.items():
        if canon in terms:
            terms[canon].add(variant)
    return terms


def _content(term: str, canonical: str, entry: dict) -> str:
    """임베딩 대상 텍스트 - 표기 + 표준명 + 해설 + 주의사항 (표기를 의미에 결합)"""
    return f"{term} {canonical} {entry.get('explanation', '')} {entry.get('caution', '')}"


def main() -> None:
    settings = load_settings()
    embedder = OpenAIEmbedder(settings.openai_api_key, settings.embed_model)

    with psycopg.connect(settings.database_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {TABLE} ("
            "id serial PRIMARY KEY, term text UNIQUE, canonical_name text, "
            f"content text, entry jsonb, embedding vector({_DIM}))"
        )

        def _upsert(term: str, canonical: str, content: str, entry: dict) -> None:
            vector = embedder.embed(content)
            conn.execute(
                f"INSERT INTO {TABLE} (term, canonical_name, content, entry, embedding) "
                "VALUES (%s, %s, %s, %s, %s::vector) "
                "ON CONFLICT (term) DO UPDATE SET "
                "canonical_name = EXCLUDED.canonical_name, content = EXCLUDED.content, "
                "entry = EXCLUDED.entry, embedding = EXCLUDED.embedding",
                (term, canonical, content, json.dumps(entry, ensure_ascii=False), vector_literal(vector)),
            )

        count = 0
        for canonical, terms in _terms_by_canonical().items():
            entry = REFERENCE[canonical]
            for term in sorted(terms):
                _upsert(term, canonical, _content(term, canonical, entry), entry)
                count += 1

        # 정성 소견 색인 - 소견별 카드(해설·주의·출처·flag), 소견 텍스트로 의미검색
        finding_count = 0
        for item, spec in FINDINGS.items():
            for keywords, flag, explanation, caution in spec["findings"]:
                term = f"{item}:{keywords[0]}"  # 항목+대표 소견어 (term UNIQUE)
                content = f"{item} {' '.join(keywords)} {explanation} {caution}"
                entry = {"explanation": explanation, "caution": caution,
                         "source": spec["source"], "flag": flag}
                _upsert(term, item, content, entry)
                finding_count += 1

        conn.commit()
        print(f"색인 완료: {count}개 표기 ({len(REFERENCE)}개 표준명) "
              f"+ {finding_count}개 정성 소견 ({len(FINDINGS)}개 항목)")


if __name__ == "__main__":
    main()
