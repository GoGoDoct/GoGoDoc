"""컴포지션 루트 - 어댑터 주입 및 객체 조립

외부 기술 구현을 한곳에서 와이어링, 상위 계층(interfaces)은 이 팩토리만 호출
"""

from gogodoc.application.pipeline import Pipeline
from gogodoc.infrastructure.config import Settings, load_settings
from gogodoc.infrastructure.llm.openai_client import OpenAILLM
from gogodoc.infrastructure.pdf.pdfplumber_parser import PdfPlumberParser
from gogodoc.infrastructure.pdf.pdf2image_renderer import Pdf2ImageRenderer
from gogodoc.infrastructure.retrieval.dict_retriever import DictRetriever


def build_retriever(settings: Settings):
    """retriever 선택 - RETRIEVER=pgvector 면 벡터 검색, 기본은 dict"""
    if settings.retriever == "pgvector" and settings.database_url:
        # 무거운 의존성(psycopg)은 필요 시에만 import
        from gogodoc.infrastructure.retrieval.pgvector_retriever import PgvectorRetriever
        from gogodoc.infrastructure.retrieval.embedder import OpenAIEmbedder

        embedder = OpenAIEmbedder(settings.openai_api_key, settings.embed_model)
        return PgvectorRetriever(
            settings.database_url,
            embedder,
            fallback=DictRetriever(),
            threshold=settings.retriever_threshold,
        )
    return DictRetriever()


def build_pipeline(settings: Settings | None = None) -> Pipeline:
    """파이프라인 조립 - 실제 어댑터 주입"""
    settings = settings or load_settings()
    return Pipeline(
        parser=PdfPlumberParser(),
        llm=OpenAILLM(settings),
        retriever=build_retriever(settings),
    )


def build_renderer(settings: Settings | None = None) -> Pdf2ImageRenderer:
    """렌더러 조립 - API 키 불필요"""
    settings = settings or load_settings()
    return Pdf2ImageRenderer(dpi=settings.render_dpi)


def build_chat_service(settings: Settings | None = None):
    """F-007 챗봇 분류·라우팅 서비스 조립 (LLM 주입)"""
    from gogodoc.application.chat_service import ChatService

    settings = settings or load_settings()
    return ChatService(OpenAILLM(settings))


def build_chat_rag_service(settings: Settings | None = None):
    """F-007 챗봇 RAG 답변 서비스 조립 (LLM 주입)"""
    from gogodoc.application.chat_rag_service import ChatRagService

    settings = settings or load_settings()
    return ChatRagService(OpenAILLM(settings))
