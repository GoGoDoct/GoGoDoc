"""해설 dict → pgvector 색인 스크립트

reference_dict 각 항목을 OpenAI 임베딩으로 벡터화하여 pgvector 에 적재
실행: python -m scripts.index_reference  (DATABASE_URL·OPENAI_API_KEY 필요)
"""

import json

import psycopg

from gogodoc.infrastructure.config import load_settings
from gogodoc.infrastructure.retrieval.embedder import OpenAIEmbedder
from gogodoc.infrastructure.retrieval.pgvector_retriever import TABLE, vector_literal
from gogodoc.domain.reference.reference_dict import REFERENCE

# text-embedding-3-small 차원
_DIM = 1536


def _content(name: str, entry: dict) -> str:
    """임베딩 대상 텍스트 - 항목명 + 해설 + 주의사항"""
    return f"{name} {entry.get('explanation', '')} {entry.get('caution', '')}"


def main() -> None:
    settings = load_settings()
    embedder = OpenAIEmbedder(settings.openai_api_key, settings.embed_model)

    with psycopg.connect(settings.database_url) as conn:
        conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
        conn.execute(
            f"CREATE TABLE IF NOT EXISTS {TABLE} ("
            "id serial PRIMARY KEY, canonical_name text UNIQUE, content text, "
            f"entry jsonb, embedding vector({_DIM}))"
        )

        count = 0
        for name, entry in REFERENCE.items():
            content = _content(name, entry)
            vector = embedder.embed(content)
            conn.execute(
                f"INSERT INTO {TABLE} (canonical_name, content, entry, embedding) "
                "VALUES (%s, %s, %s, %s::vector) "
                "ON CONFLICT (canonical_name) DO UPDATE SET "
                "content = EXCLUDED.content, entry = EXCLUDED.entry, embedding = EXCLUDED.embedding",
                (name, content, json.dumps(entry, ensure_ascii=False), vector_literal(vector)),
            )
            count += 1
        conn.commit()
        print(f"색인 완료: {count}개 항목")


if __name__ == "__main__":
    main()
