"""Streamlit UI - split 뷰 (원본 PDF 좌 / 해석 결과 우)"""

import tempfile
from pathlib import Path

import streamlit as st

from gogodoc.composition import build_pipeline, build_renderer
from gogodoc.infrastructure.config import load_settings
from gogodoc.infrastructure.db.init_db import init_db
from gogodoc.infrastructure.pdf import (
    PdfValidationError,
    validate_digital_pdf,
    validate_uploaded_pdf_metadata,
)
from gogodoc.domain.models import UserProfile, Sex, Flag, FinalReport
from gogodoc.application.auth_service import login, register, AuthError, DuplicateNameError

# 플래그별 표시 라벨
_FLAG_LABEL = {
    Flag.NORMAL: "정상",
    Flag.CAUTION: "주의",
    Flag.ABNORMAL: "이상",
    Flag.EMERGENCY: "응급",
    Flag.CHECK_NEEDED: "확인필요",
    Flag.UNKNOWN: "알수없음",
}


def _render_result(report: FinalReport) -> None:
    """해석 결과 렌더링"""
    # 응급 이상치 최우선 표시
    for alert in report.emergency_alerts:
        st.error(alert)

    # 부분 실패 등 비치명적 이슈 안내
    for note in report.notes:
        st.warning(note)

    for item in report.items:
        label = _FLAG_LABEL.get(item.flag, "")
        with st.container(border=True):
            st.markdown(f"**{item.canonical_name}** · {label}")
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


def _render_login(pool) -> None:
    """로그인 페이지"""
    st.title("GoGoDoc 로그인")
    st.text_input("이름", key="login_name")
    st.text_input("비밀번호", type="password", key="login_pw")

    if st.button("로그인"):
        name = st.session_state.login_name
        pw = st.session_state.login_pw
        if not name or not pw:
            st.warning("이름과 비밀번호를 입력하세요")
            return
        try:
            user = login(pool, name, pw)
            st.session_state.authenticated = True
            st.session_state.user_name = user["name"]
            st.session_state.sex = user["sex"]
            st.session_state.age = user["age"]
            st.rerun()
        except AuthError:
            st.error("이름 또는 비밀번호가 올바르지 않습니다")

    if st.button("회원가입"):
        st.session_state.page = "signup"
        st.rerun()


def _render_signup(pool) -> None:
    """회원가입 페이지"""
    st.title("GoGoDoc 회원가입")
    st.text_input("이름", key="signup_name")
    st.text_input("비밀번호", type="password", key="signup_pw")
    st.radio("성별", ["남성", "여성"], horizontal=True, key="signup_sex")
    st.number_input("나이", min_value=0, max_value=120, value=40, key="signup_age")
    st.text_input("거주지", placeholder="예) 서울특별시 강남구", key="signup_location")

    if st.button("가입"):
        name = st.session_state.signup_name
        pw = st.session_state.signup_pw
        if not name or not pw:
            st.warning("모든 항목을 입력하세요")
            return
        sex = "male" if st.session_state.signup_sex == "남성" else "female"
        age = st.session_state.signup_age
        location = st.session_state.get("signup_location", "")
        try:
            register(pool, name, pw, sex, age, location)
            user = login(pool, name, pw)
            st.session_state.authenticated = True
            st.session_state.page = "login"
            st.session_state.user_name = user["name"]
            st.session_state.sex = user["sex"]
            st.session_state.age = user["age"]
            st.session_state.location = user.get("location", "")
            st.rerun()
        except DuplicateNameError:
            st.error("이미 사용 중인 이름입니다")

    if st.button("로그인으로 돌아가기"):
        st.session_state.page = "login"
        st.rerun()


def _render_main(settings, pool) -> None:
    """메인 분석 화면"""
    st.title("종합검진 결과 AI 해석")

    # 사이드바 상단 사용자 정보 및 로그아웃
    st.sidebar.write(f"안녕하세요, {st.session_state.user_name}님")
    if st.sidebar.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

    # 성별·나이 입력 (정상범위 판정 기준)
    st.sidebar.header("기본 정보")
    sex = Sex.MALE if st.session_state.sex == "male" else Sex.FEMALE
    age = st.session_state.age
    profile = UserProfile(sex=sex, age=age)
    st.sidebar.caption("업로드 PDF 는 세션 내 처리 후 즉시 삭제 - 서버 미저장")

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


def main() -> None:
    st.set_page_config(page_title="GoGoDoc - 검진 결과 해석", layout="wide")

    # 세션 상태 초기화
    _DEFAULTS = {
        "page": "login",
        "authenticated": False,
        "user_name": "",
        "sex": "male",
        "age": 40,
    }
    for k, v in _DEFAULTS.items():
        st.session_state.setdefault(k, v)

    settings = load_settings()

    # DB 초기화
    try:
        pool = init_db(settings)
    except Exception:
        st.error("데이터베이스 연결에 실패했습니다. .env 설정을 확인하세요")
        st.stop()

    # 페이지 라우팅
    if not st.session_state.authenticated:
        if st.session_state.page == "signup":
            _render_signup(pool)
        else:
            _render_login(pool)
    else:
        _render_main(settings, pool)


if __name__ == "__main__":
    main()
