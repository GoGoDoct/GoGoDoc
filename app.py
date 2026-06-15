# -*- coding: utf-8 -*-
"""GoGoDoc — 종합검진 결과 AI 해석 서비스 (Streamlit).

실행:  streamlit run streamlit_app/app.py

페이지 라우팅(session_state.page): login → signup → dashboard → analysis
- login/signup : 인증 화면 (좌측 브랜드 패널 + 폼)
- dashboard    : 건강 요약 / 추이 / 검진 기록 / 추적 관찰
- analysis     : PDF 업로드 → 4단계 파이프라인 → 원본/AI 해석 split 뷰
"""
import time
import streamlit as st

from styles import inject_css
from sample_data import STATUS, RECORDS, TRACKED, FBS_TREND
from pipeline import run_pipeline
import ui

st.set_page_config(page_title="GoGoDoc — 검진 결과 AI 해석", page_icon="🫆", layout="wide")
inject_css(st)

# ── 세션 기본값 ──────────────────────────────────────────
_defaults = dict(page="login", gender="male", age=40, analyzed=False,
                 emergency=False, item_filter="전체 항목", file=None)
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)


def go(page: str):
    st.session_state.page = page
    st.rerun()


# ══════════════════════════════════════════════════════════
# 로그인 / 회원가입
# ══════════════════════════════════════════════════════════
def _auth_layout_css():
    # 좌측 고정 풀하이트 패널 옆으로 본문 밀기 (가운데 정렬 아님)
    st.markdown(
        "<style>.block-container{max-width:100%!important;"
        "padding:0 3rem 2rem calc(26vw + 3rem)!important}</style>",
        unsafe_allow_html=True,
    )


def render_login():
    _auth_layout_css()
    st.markdown(ui.brand_panel_html(), unsafe_allow_html=True)
    _l, mid, _r = st.columns([1.2, 1, 1.2])
    with mid:
        st.markdown('<div style="height:14vh"></div>', unsafe_allow_html=True)
        st.markdown('<h2 style="font-size:27px;font-weight:800;margin:0">로그인</h2>'
                    '<p style="font-size:14px;color:#7B8597;margin:9px 0 18px">'
                    '검진 기록과 해석 결과를 한곳에서 관리하세요.</p>', unsafe_allow_html=True)
        st.text_input("이메일", placeholder="name@example.com", key="login_email")
        st.text_input("비밀번호", type="password", placeholder="••••••••", key="login_pw")
        st.checkbox("로그인 상태 유지", value=True)
        if st.button("로그인", type="primary", use_container_width=True):
            go("dashboard")
        st.markdown('<div style="text-align:center;font-size:13.5px;color:#7B8597;margin-top:16px">'
                    '계정이 없으신가요?</div>', unsafe_allow_html=True)
        if st.button("회원가입", use_container_width=True):
            go("signup")


def render_signup():
    _auth_layout_css()
    st.markdown(ui.brand_panel_html(), unsafe_allow_html=True)
    _l, mid, _r = st.columns([0.7, 1, 0.7])
    with mid:
        st.markdown('<div style="height:5vh"></div>', unsafe_allow_html=True)
        st.markdown('<h2 style="font-size:27px;font-weight:800;margin:0">회원가입</h2>'
                    '<p style="font-size:14px;color:#7B8597;margin:9px 0 14px">'
                    '성별·나이는 정상 범위 판정 기준으로 사용됩니다.</p>', unsafe_allow_html=True)
        st.text_input("이름", placeholder="홍길동")
        st.text_input("이메일", placeholder="name@example.com")
        c1, c2 = st.columns(2)
        c1.text_input("비밀번호", type="password", placeholder="8자 이상")
        c2.text_input("비밀번호 확인", type="password", placeholder="다시 입력")
        c3, c4 = st.columns([1.4, 1])
        with c3:
            g = st.radio("성별", ["남성", "여성"], horizontal=True,
                         index=0 if st.session_state.gender == "male" else 1)
            st.session_state.gender = "male" if g == "남성" else "female"
        with c4:
            st.session_state.age = st.number_input("나이", 1, 120, st.session_state.age)
        st.checkbox("서비스 이용약관 및 개인정보 처리방침에 동의합니다.", value=True)
        if st.button("가입하고 시작하기", type="primary", use_container_width=True):
            go("dashboard")
        st.markdown('<div style="text-align:center;font-size:13.5px;color:#7B8597;margin-top:14px">'
                    '이미 계정이 있으신가요?</div>', unsafe_allow_html=True)
        if st.button("로그인", use_container_width=True, key="to_login"):
            go("login")


# ══════════════════════════════════════════════════════════
# 대시보드
# ══════════════════════════════════════════════════════════
def render_dashboard():
    # 사이드바 페이지 본문 전체 폭·좌측 정렬 (사이드바와 본문 사이 빈 공간 제거)
    st.markdown("<style>.block-container{max-width:100%!important}</style>", unsafe_allow_html=True)
    with st.sidebar:
        _sidebar_brand()
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
        st.markdown(ui.sidebar_nav_html("dashboard"), unsafe_allow_html=True)
        st.markdown('<div style="height:40vh"></div>', unsafe_allow_html=True)
        st.markdown(ui.sidebar_profile_html(), unsafe_allow_html=True)
        if st.button("로그아웃", use_container_width=True):
            go("login")

    head, btn = st.columns([3, 1])
    with head:
        st.markdown('<h1 style="font-size:25px;font-weight:800;margin:0">안녕하세요, 홍길동님 👋</h1>'
                    '<p style="font-size:14px;color:#7B8597;margin:8px 0 0">'
                    '최근 검진일 2026-06-10 기준, 건강 요약을 정리했어요.</p>', unsafe_allow_html=True)
    with btn:
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        if st.button("＋ 새 검진 해석하기", type="primary", use_container_width=True):
            st.session_state.analyzed = False
            go("analysis")

    st.markdown(ui.kpi_cards_html(8, 4, 7, 1), unsafe_allow_html=True)
    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)

    left, right = st.columns([1.4, 1], gap="medium")
    with left:
        st.markdown('<div class="gg-card" style="padding:22px 24px 8px">'
                    '<div style="font-size:15px;font-weight:800">공복혈당 추이</div>'
                    '<div style="font-size:12.5px;color:#8590A1;margin-top:4px">'
                    '최근 4회 검진 · 단위 mg/dL · <span style="color:#B26A00;font-weight:700">상승 추세</span></div>',
                    unsafe_allow_html=True)
        st.markdown(ui.fbs_chart_svg_html(FBS_TREND), unsafe_allow_html=True)
        st.markdown('<div style="font-size:12.5px;color:#7B8597;line-height:1.6;background:#F8FAFC;'
                    'border-radius:10px;padding:11px 13px;margin-bottom:16px">3년간 꾸준히 상승해 올해 정상 상한(99)을 '
                    '넘었어요. 식이·운동 관리로 되돌릴 수 있는 <b style="color:#B26A00">공복혈당장애 경계</b> 단계입니다.</div></div>',
                    unsafe_allow_html=True)
        st.markdown(ui.records_html(RECORDS), unsafe_allow_html=True)
    with right:
        st.markdown(ui.tracked_html(TRACKED), unsafe_allow_html=True)
        st.markdown(ui.next_checkup_html(), unsafe_allow_html=True)
        st.markdown(ui.disclaimer_html(), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# 검진 결과 AI 해석 (업로드 → 파이프라인 → split 뷰)
# ══════════════════════════════════════════════════════════
def render_analysis():
    # 사이드바 페이지 본문 전체 폭·좌측 정렬 (사이드바와 본문 사이 빈 공간 제거)
    st.markdown("<style>.block-container{max-width:100%!important}</style>", unsafe_allow_html=True)
    with st.sidebar:
        _sidebar_brand()
        st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)
        if st.button("← 대시보드", use_container_width=True):
            go("dashboard")
        st.markdown('<div style="font-size:12px;font-weight:700;color:#9099A8;margin:18px 0 4px">기본 정보</div>',
                    unsafe_allow_html=True)
        g = st.radio("성별", ["남성", "여성"], horizontal=True,
                     index=0 if st.session_state.gender == "male" else 1)
        st.session_state.gender = "male" if g == "남성" else "female"
        st.session_state.age = st.number_input("나이", 1, 120, st.session_state.age)
        st.markdown('<div style="background:#F1F5FB;border:1px solid #E2EAF4;border-radius:12px;'
                    'padding:13px 14px;margin-top:18px;font-size:11.5px;line-height:1.6;color:#6B7588">'
                    '🔒 <b style="color:#15448A">개인정보 보호</b><br>업로드한 PDF는 세션 내에서만 처리되며 '
                    '서버에 저장되지 않고 즉시 삭제됩니다.</div>', unsafe_allow_html=True)

    if not st.session_state.analyzed:
        _render_upload()
    else:
        _render_result()


def _render_upload():
    body = st.columns([2.4, 1])[0]
    with body:
        st.markdown('<div style="display:inline-flex;align-items:center;gap:7px;padding:6px 13px;'
                    'background:#EAF1FA;border-radius:999px;font-size:12.5px;font-weight:600;color:#15448A">'
                    '● AI 검진 해석 비서</div>'
                    '<h1 style="font-size:34px;font-weight:800;letter-spacing:-1px;margin:16px 0 0;line-height:1.25">'
                    '종합검진 결과,<br>쉬운 말로 풀어드립니다</h1>'
                    '<p style="font-size:15px;color:#5B6678;line-height:1.65;margin:14px 0 0;max-width:560px">'
                    '검진 결과지 PDF를 올리면 검사 수치를 일반인이 이해할 수 있게 해설하고, '
                    '신경 써야 할 항목과 다음 검진 때 추적할 항목을 정리해 드려요.</p>', unsafe_allow_html=True)
        st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)

        with st.container(border=True):
            st.markdown('<div style="font-size:13.5px;font-weight:700;color:#4A5567;margin-bottom:8px">'
                        '검진 결과지 PDF 업로드</div>', unsafe_allow_html=True)
            uploaded = st.file_uploader("PDF 업로드", type=["pdf"], label_visibility="collapsed")
            if uploaded is not None:
                _run_and_store(uploaded)
            st.markdown('<div style="text-align:center;color:#A4ACBA;font-size:12px;margin:8px 0 6px">또는</div>',
                        unsafe_allow_html=True)
            if st.button("📄  샘플 결과지로 체험해보기", use_container_width=True):
                _run_and_store(None)

        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        st.markdown(ui.feature_cards_html(), unsafe_allow_html=True)


def _run_and_store(file):
    steps = ["검진 결과지 파싱 · 항목 추출", "정상 범위 매칭 (성별·나이 기준)",
             "AI 근거 기반 해석 생성", "안전 검토 · 요약 정리"]
    with st.status("결과지를 분석하고 있어요", expanded=True) as status:
        for s in steps:
            st.write(f"✓ {s}")
            time.sleep(0.6)
        status.update(label="해석 완료", state="complete")
    st.session_state.file = file
    st.session_state.analyzed = True
    st.rerun()


def _render_result():
    res = run_pipeline(st.session_state.file, st.session_state.gender,
                       st.session_state.age, st.session_state.emergency)
    counts = res["counts"]

    head, pills = st.columns([2, 1])
    with head:
        sub = ("응급 이상치가 포함되어 있어요. 아래 안내에 따라 즉시 의료기관에 내원하세요."
               if res["emergency"] else
               "정상 범위를 벗어난 항목이 있어요. 추적 관찰을 권장합니다."
               if counts["이상"] or counts["주의"] else "모든 항목이 정상 범위 안에 있어요.")
        st.markdown(f'<h2 style="font-size:23px;font-weight:800;margin:0">검진 결과 해석'
                    f'<span style="font-size:12px;font-weight:600;color:#5B6678;background:#F0F3F8;'
                    f'border:1px solid #E4E9F0;border-radius:8px;padding:4px 10px;margin-left:10px">'
                    f'📄 종합검진_결과지.pdf</span></h2>'
                    f'<div style="font-size:13.5px;color:#5B6678;margin-top:7px">{sub}</div>',
                    unsafe_allow_html=True)
    with pills:
        st.markdown(ui.summary_pills_html(counts["정상"], counts["주의"], counts["이상"]),
                    unsafe_allow_html=True)

    if res["emergency"]:
        st.markdown(ui.emergency_banner_html(res["emergency"]), unsafe_allow_html=True)

    f1, f2, f3 = st.columns([1.4, 1, 1])
    with f1:
        st.session_state.item_filter = st.radio(
            "필터", ["전체 항목", "주의·이상만"], horizontal=True, label_visibility="collapsed",
            index=0 if st.session_state.item_filter == "전체 항목" else 1)
    with f2:
        st.session_state.emergency = st.toggle("응급 시나리오 보기", value=st.session_state.emergency)
    with f3:
        if st.button("↻  다시 업로드", use_container_width=True):
            st.session_state.update(analyzed=False, file=None, emergency=False)
            st.rerun()

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    items = res["items"]
    shown = items if st.session_state.item_filter == "전체 항목" else [
        it for it in items if it["status"] != "정상"]

    left, right = st.columns([0.92, 1.08], gap="medium")
    with left:
        st.markdown('<div style="font-size:12.5px;font-weight:700;color:#9099A8;margin-bottom:9px">'
                    '📄 원본 검진 결과지</div>', unsafe_allow_html=True)
        gender_short = "남" if st.session_state.gender == "male" else "여"
        st.markdown(ui.report_table_html(items, gender_short, st.session_state.age),
                    unsafe_allow_html=True)
    with right:
        st.markdown('<div style="font-size:12.5px;font-weight:700;color:#15448A;margin-bottom:9px">'
                    '💡 AI 해석</div>', unsafe_allow_html=True)
        for it in shown:
            st.markdown(ui.result_card_html(it), unsafe_allow_html=True)
        # 추적 권장 항목
        chips = "".join(
            f'<span style="background:rgba(255,255,255,.14);border:1px solid rgba(255,255,255,.22);'
            f'border-radius:8px;padding:7px 12px;font-size:12.5px;font-weight:600">{t}</span>'
            for t in res["tracked"])
        st.markdown('<div style="background:#15448A;border-radius:14px;padding:18px 20px;color:#fff">'
                    '<div style="font-size:14px;font-weight:800">📈 다음 검진 때 추적 권장 항목</div>'
                    f'<div style="display:flex;flex-wrap:wrap;gap:8px;margin-top:13px">{chips}</div>'
                    '<div style="font-size:12px;opacity:.88;margin-top:13px;line-height:1.6">'
                    '위 항목은 약 3개월 후 재검을 권장해요. 생활습관 관리만으로 충분히 개선될 수 있는 단계입니다.</div></div>',
                    unsafe_allow_html=True)
        st.markdown(ui.disclaimer_html(), unsafe_allow_html=True)


def _sidebar_brand():
    logo = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M3 12h4l2.5 7 4-14 2.5 7H21"/></svg>')
    st.markdown('<div style="display:flex;align-items:center;gap:11px;padding:4px 0">'
                '<div style="width:38px;height:38px;border-radius:11px;'
                'background:linear-gradient(150deg,#1B5AA8,#10366E);display:flex;align-items:center;'
                f'justify-content:center">{logo}</div>'
                '<div><div style="font-size:17px;font-weight:800;line-height:1">GoGoDoc</div>'
                '<div style="font-size:11px;color:#7B8597;margin-top:3px">검진 결과 AI 해석</div></div></div>',
                unsafe_allow_html=True)


# ── 라우터 ───────────────────────────────────────────────
PAGES = {"login": render_login, "signup": render_signup,
         "dashboard": render_dashboard, "analysis": render_analysis}
PAGES.get(st.session_state.page, render_login)()
