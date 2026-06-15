"""pdfplumber 파서 테스트"""

from gogodoc.infrastructure.pdf import pdfplumber_parser
from gogodoc.infrastructure.pdf.pdfplumber_parser import PdfPlumberParser


class FakePdf:
    def __init__(self, pages):
        self.pages = pages

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class FakePage:
    def __init__(self, tables=None, text=""):
        self._tables = tables or []
        self._text = text

    def extract_tables(self):
        return self._tables

    def extract_text(self):
        return self._text


def test_pdfplumber_parser_extracts_tables():
    original_open = pdfplumber_parser.pdfplumber.open
    pdfplumber_parser.pdfplumber.open = lambda _: FakePdf(
        [
            FakePage(
                tables=[
                    [
                        ["검사항목", "결과", "단위"],
                        ["ALT", "45", "U/L"],
                    ]
                ]
            )
        ]
    )
    try:
        text = PdfPlumberParser().extract_text("dummy.pdf")
    finally:
        pdfplumber_parser.pdfplumber.open = original_open

    assert "[page 1]" in text
    assert "ALT\t45\tU/L" in text


def test_pdfplumber_parser_falls_back_to_text():
    original_open = pdfplumber_parser.pdfplumber.open
    pdfplumber_parser.pdfplumber.open = lambda _: FakePdf(
        [FakePage(tables=[], text="공복혈당 101 mg/dL")]
    )
    try:
        text = PdfPlumberParser().extract_text("dummy.pdf")
    finally:
        pdfplumber_parser.pdfplumber.open = original_open

    assert "공복혈당 101 mg/dL" in text
