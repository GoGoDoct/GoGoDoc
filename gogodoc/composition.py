"""컴포지션 루트 - 어댑터 주입 및 객체 조립

외부 기술 구현을 한곳에서 와이어링, 상위 계층(interfaces)은 이 팩토리만 호출
"""

from gogodoc.application.pipeline import Pipeline
from gogodoc.infrastructure.config import Settings, load_settings
from gogodoc.infrastructure.llm.openai_client import OpenAILLM
from gogodoc.infrastructure.pdf.pdfplumber_parser import PdfPlumberParser
from gogodoc.infrastructure.pdf.pdf2image_renderer import Pdf2ImageRenderer


def build_pipeline(settings: Settings | None = None) -> Pipeline:
    """파이프라인 조립 - 실제 어댑터 주입"""
    settings = settings or load_settings()
    return Pipeline(
        parser=PdfPlumberParser(),
        llm=OpenAILLM(settings),
    )


def build_renderer(settings: Settings | None = None) -> Pdf2ImageRenderer:
    """렌더러 조립 - API 키 불필요"""
    settings = settings or load_settings()
    return Pdf2ImageRenderer(dpi=settings.render_dpi)
