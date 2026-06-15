"""pdfplumber 어댑터 - PdfParserPort 구현"""

import pdfplumber

from gogodoc.infrastructure.pdf.ingestion import PdfValidationError


class PdfPlumberParser:
    """pdfplumber 기반 PDF 텍스트·표 추출"""

    def extract_text(self, pdf_path: str) -> str:
        """표 추출 우선, 실패 시 텍스트 폴백"""
        chunks: list[str] = []
        try:
            with pdfplumber.open(pdf_path) as pdf:
                for page_index, page in enumerate(pdf.pages, start=1):
                    page_chunks: list[str] = []
                    tables = page.extract_tables() or []
                    for table in tables:
                        for row in table:
                            cells = [str(cell or "").strip() for cell in row]
                            if any(cells):
                                page_chunks.append("\t".join(cells))

                    if not page_chunks:
                        text = page.extract_text() or ""
                        if text.strip():
                            page_chunks.append(text.strip())

                    if page_chunks:
                        chunks.append(f"[page {page_index}]\n" + "\n".join(page_chunks))
        except Exception as exc:
            raise PdfValidationError("PDF에서 검사항목을 추출할 수 없습니다.") from exc

        text = "\n\n".join(chunks).strip()
        if not text:
            raise PdfValidationError("검사항목을 찾을 수 없습니다. PDF 파일을 확인하세요.")
        return text
