"""pdfplumber 어댑터 - PdfParserPort 구현"""

import pdfplumber


class PdfPlumberParser:
    """pdfplumber 기반 PDF 텍스트·표 추출"""

    def extract_text(self, pdf_path: str) -> str:
        """표 추출 우선, 실패 시 텍스트 폴백"""
        chunks: list[str] = []
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                table = page.extract_table()
                if table:
                    # 표 행을 탭 구분 텍스트로 평탄화
                    for row in table:
                        cells = [c or "" for c in row]
                        chunks.append("\t".join(cells))
                else:
                    # 표 인식 실패 시 텍스트 폴백
                    chunks.append(page.extract_text() or "")
        return "\n".join(chunks)
