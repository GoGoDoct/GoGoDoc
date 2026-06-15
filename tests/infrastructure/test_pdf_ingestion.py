"""PDF 업로드 검증 테스트"""

from gogodoc.infrastructure.pdf.ingestion import (
    MAX_PDF_SIZE_BYTES,
    PdfValidationError,
    validate_uploaded_pdf_metadata,
)


def test_validate_uploaded_pdf_metadata_accepts_pdf():
    validate_uploaded_pdf_metadata("result.pdf", "application/pdf", 1024)


def test_validate_uploaded_pdf_metadata_rejects_non_pdf_extension():
    try:
        validate_uploaded_pdf_metadata("result.png", "application/pdf", 1024)
    except PdfValidationError as exc:
        assert "PDF" in exc.message
    else:
        raise AssertionError("PdfValidationError not raised")


def test_validate_uploaded_pdf_metadata_rejects_non_pdf_mime():
    try:
        validate_uploaded_pdf_metadata("result.pdf", "image/png", 1024)
    except PdfValidationError as exc:
        assert "PDF" in exc.message
    else:
        raise AssertionError("PdfValidationError not raised")


def test_validate_uploaded_pdf_metadata_rejects_large_file():
    try:
        validate_uploaded_pdf_metadata(
            "result.pdf",
            "application/pdf",
            MAX_PDF_SIZE_BYTES + 1,
        )
    except PdfValidationError as exc:
        assert "20MB" in exc.message
    else:
        raise AssertionError("PdfValidationError not raised")
