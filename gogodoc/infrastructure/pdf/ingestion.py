"""PDF 업로드 검증 유틸리티"""

from dataclasses import dataclass
from pathlib import Path

import pdfplumber


MAX_PDF_SIZE_BYTES = 20 * 1024 * 1024
PDF_MIME_TYPE = "application/pdf"


class PdfValidationError(ValueError):
    """사용자에게 표시 가능한 PDF 검증 오류"""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


@dataclass(frozen=True)
class PdfUploadInfo:
    """검증 완료된 PDF 메타데이터"""

    filename: str
    size_bytes: int
    page_count: int


def validate_uploaded_pdf_metadata(
    filename: str,
    content_type: str | None,
    size_bytes: int,
) -> None:
    """업로드 파일명, MIME, 크기 검증"""
    if Path(filename).suffix.lower() != ".pdf":
        raise PdfValidationError("지원하지 않는 파일 형식입니다. PDF 파일만 업로드하세요.")

    if content_type and content_type != PDF_MIME_TYPE:
        raise PdfValidationError("지원하지 않는 파일 형식입니다. PDF 파일만 업로드하세요.")

    if size_bytes > MAX_PDF_SIZE_BYTES:
        raise PdfValidationError("파일 크기 제한을 초과했습니다. 20MB 이하 PDF를 사용하세요.")


def validate_digital_pdf(pdf_path: str, filename: str, size_bytes: int) -> PdfUploadInfo:
    """PDF 열기 가능 여부와 텍스트 레이어 존재 여부 검증"""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            page_count = len(pdf.pages)
            has_text_layer = any((page.extract_text() or "").strip() for page in pdf.pages)
    except Exception as exc:
        raise PdfValidationError("파일을 열 수 없습니다. PDF 파일이 손상되었는지 확인하세요.") from exc

    if not has_text_layer:
        raise PdfValidationError("디지털 PDF만 지원합니다. 스캔본은 지원하지 않습니다.")

    return PdfUploadInfo(
        filename=filename,
        size_bytes=size_bytes,
        page_count=page_count,
    )
