"""환경 변수 로딩 - 설정 값객체"""

import os
from dataclasses import dataclass

from dotenv import load_dotenv

# .env 로딩
load_dotenv()


@dataclass(frozen=True)
class Settings:
    """런타임 설정"""

    openai_api_key: str
    parse_model: str  # 파싱용 OpenAI 모델
    interpret_model: str  # 해석용 OpenAI 모델
    render_dpi: int
    db_host: str
    db_port: int
    db_name: str
    db_user: str
    db_password: str
    retriever: str  # 근거 검색 방식 - "dict" | "pgvector"
    database_url: str  # pgvector Postgres 연결 (retriever=pgvector 시)
    embed_model: str  # 임베딩 모델
    retriever_threshold: float  # 벡터 코사인 거리 임계값 - 초과 시 미수록(OOV) 처리
    hira_api_key: str  # HIRA API 키


def load_settings() -> Settings:
    """환경 변수에서 설정 로딩 - 키 누락 시 빈 문자열 (UI 에서 검증)"""
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        parse_model=os.getenv("PARSE_MODEL", "gpt-4o-mini"),
        interpret_model=os.getenv("INTERPRET_MODEL", "gpt-4o-mini"),
        render_dpi=int(os.getenv("RENDER_DPI", "150")),
        db_host=os.getenv("DB_HOST", "localhost"),
        db_port=int(os.getenv("DB_PORT", "5432")),
        db_name=os.getenv("DB_NAME", "gogodoc"),
        db_user=os.getenv("DB_USER", "postgres"),
        db_password=os.getenv("DB_PASSWORD", ""),
        retriever=os.getenv("RETRIEVER", "dict"),
        database_url=os.getenv("DATABASE_URL", ""),
        embed_model=os.getenv("EMBED_MODEL", "text-embedding-3-small"),
        retriever_threshold=float(os.getenv("RETRIEVER_THRESHOLD", "0.55")),  # 실측 캘리브레이션 - 0.45→0.55
        hira_api_key=os.getenv("HIRA_API_KEY", ""),
    )
