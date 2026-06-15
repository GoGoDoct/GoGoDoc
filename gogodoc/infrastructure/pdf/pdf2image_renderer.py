"""pdf2image 어댑터 - RendererPort 구현 (poppler 필요)"""

from pdf2image import convert_from_path


class Pdf2ImageRenderer:
    """pdf2image 기반 PDF 페이지 렌더링"""

    def __init__(self, dpi: int = 150) -> None:
        self._dpi = dpi

    def render_pages(self, pdf_path: str) -> list:
        """페이지를 PIL 이미지 목록으로 변환"""
        return convert_from_path(pdf_path, dpi=self._dpi)
