"""Streamlit UI - split 뷰 (원본 PDF 좌 / 해석 결과 우)"""

import tempfile
from pathlib import Path

import streamlit as st

from gogodoc.composition import build_pipeline, build_renderer
from gogodoc.infrastructure.config import load_settings
from gogodoc.infrastructure.pdf import (
    PdfValidationError,
    validate_digital_pdf,
    validate_uploaded_pdf_metadata,
)
from gogodoc.domain.models import UserProfile, Sex, Flag, FinalReport

# 플래그별 표시 라벨·아이콘
_FLAG_BADGE = {
    Flag.NORMAL: ("정상", "🟢"),
    Flag.CAUTION: ("주의", "🟡"),
    Flag.ABNORMAL: ("이상", "🔴"),
    Flag.EMERGENCY: ("응급", "🚨"),
    Flag.UNKNOWN: ("판정불가", "⚪"),
}


def _sidebar() -> UserProfile:
    """단계 0 - 성별·나이 입력 (정상범위 판정 기준)"""
    st.sidebar.header("기본 정보")
    sex_label = st.sidebar.radio("성별", ["남성", "여성"], horizontal=True)
    age = st.sidebar.number_input("나이", min_value=0, max_value=120, value=40)
    st.sidebar.caption("업로드 PDF 는 세션 내 처리 후 즉시 삭제 - 서버 미저장")
    sex = Sex.MALE if sex_label == "남성" else Sex.FEMALE
    return UserProfile(sex=sex, age=int(age))


def _render_result(report: FinalReport) -> None:
    """해석 결과 렌더링"""
    # 응급 이상치 최우선 표시
    for alert in report.emergency_alerts:
        st.error(f"🚨 {alert}")

    for item in report.items:
        label, icon = _FLAG_BADGE.get(item.flag, ("", ""))
        with st.container(border=True):
            st.markdown(f"**{icon} {item.canonical_name}** · {label}")
            value_str = f"{item.value} {item.unit or ''}".strip()
            st.caption(f"측정값 {value_str}")
            st.write(item.explanation)
            if item.source:
                st.caption(f"출처 {item.source}")

    if report.tracking_items:
        st.subheader("추적 권장 항목")
        st.write(", ".join(report.tracking_items))

    # 면책 문구 강제 표시
    st.info(report.disclaimer)


def main() -> None:
    st.set_page_config(page_title="GoGoDoc - 검진 결과 해석", layout="wide")
    st.title("종합검진 결과 AI 해석")

    settings = load_settings()
    profile = _sidebar()
    uploaded = st.file_uploader("검진 결과지 PDF 업로드", type=["pdf"])

    if not uploaded:
        st.info("PDF 를 업로드하면 해석을 시작합니다")
        return

    try:
        validate_uploaded_pdf_metadata(
            filename=uploaded.name,
            content_type=uploaded.type,
            size_bytes=uploaded.size,
        )
    except PdfValidationError as exc:
        st.error(exc.message)
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(uploaded.getvalue())
        pdf_path = tmp.name

    try:
        try:
            pdf_info = validate_digital_pdf(
                pdf_path=pdf_path,
                filename=uploaded.name,
                size_bytes=uploaded.size,
            )
        except PdfValidationError as exc:
            st.error(exc.message)
            return

        st.sidebar.caption(f"파일명 {pdf_info.filename}")
        st.sidebar.caption(f"페이지 수 {pdf_info.page_count}")

        left, right = st.columns(2)

        # 좌측 - 원본 PDF 렌더링
        with left:
            st.subheader("원본 결과지")
            try:
                for img in build_renderer(settings).render_pages(pdf_path):
                    st.image(img, use_container_width=True)
            except Exception as exc:
                st.warning(f"원본 렌더링 실패 - poppler 설치 확인 필요 ({exc})")

        # 우측 - 해석 결과
        with right:
            st.subheader("AI 해석")
            if not settings.openai_api_key:
                st.error("OPENAI_API_KEY 미설정 - .env 확인 필요")
                return
            with st.spinner("해석 중..."):
                try:
                    report = build_pipeline(settings).run(pdf_path, profile)
                except PdfValidationError as exc:
                    st.error(exc.message)
                    return
            _render_result(report)
    finally:
        # 처리 후 임시 파일 즉시 삭제
        Path(pdf_path).unlink(missing_ok=True)


if __name__ == "__main__":
    main()
