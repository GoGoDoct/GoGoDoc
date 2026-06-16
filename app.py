# -*- coding: utf-8 -*-
"""GoGoDoc — 종합검진 결과 AI 해석 서비스 (Streamlit).

실행:  streamlit run app.py

페이지 라우팅(session_state.page):
  login → signup → dashboard → analysis → records → track → settings
"""
import time
import tempfile
from datetime import timedelta
from pathlib import Path

import streamlit as st

from styles import inject_css
from sample_data import STATUS
import ui

from gogodoc.infrastructure.config import load_settings
from gogodoc.infrastructure.db.init_db import init_db
from gogodoc.infrastructure.db.connection import get_conn, put_conn
from gogodoc.infrastructure.db.analysis_repository import (
    save as save_analysis,
    find_latest,
    find_by_user,
    delete_by_id as delete_analysis,
)
from gogodoc.infrastructure.db.user_repository import update as update_user
from gogodoc.application.auth_service import login, register, AuthError, DuplicateNameError
from gogodoc.composition import build_pipeline, build_renderer
from gogodoc.infrastructure.pdf import (
    PdfValidationError,
    validate_uploaded_pdf_metadata,
    validate_digital_pdf,
)
from gogodoc.domain.models import UserProfile, Sex, Flag

# ── 카테고리 매핑 ─────────────────────────────────────────
_CAT_MAP = {
    "AST": "간기능", "ALT": "간기능", "γ-GTP": "간기능", "GTP": "간기능",
    "공복혈당": "당대사", "당화혈색소": "당대사",
    "총콜레스테롤": "지질", "LDL": "지질", "HDL": "지질", "중성지방": "지질",
    "크레아티닌": "신장", "사구체여과율": "신장",
    "혈색소": "혈액", "헤마토크릿": "혈액",
}


def _get_cat(name: str) -> str:
    for key, cat in _CAT_MAP.items():
        if key in name:
            return cat
    return "기타"


# 생활습관으로 개선하기 어려운 항목 키워드 (토글 상세 해석 제외 대상)
_NON_CHANGEABLE = {"신장", "시력"}

# Korean status → English flag (hospital_service 호환)
_STATUS_TO_FLAG = {
    "정상": "normal",
    "주의": "caution",
    "이상": "abnormal",
    "응급": "emergency",
}


def _is_changeable(name: str) -> bool:
    return not any(kw in name for kw in _NON_CHANGEABLE)


# ── 어댑터 ───────────────────────────────────────────────
_FLAG_STATUS = {
    Flag.NORMAL: "정상",
    Flag.CAUTION: "주의",
    Flag.ABNORMAL: "이상",
    Flag.EMERGENCY: "응급",
    Flag.CHECK_NEEDED: "주의",
    Flag.UNKNOWN: "주의",
}


def _report_to_result(report, filename: str = "") -> dict:
    """FinalReport → session_state.result 형식 변환"""
    items = []
    for item in report.items:
        status = _FLAG_STATUS.get(item.flag, "주의")
        val = item.value
        items.append({
            "id": item.canonical_name,
            "cat": _get_cat(item.canonical_name),
            "name": item.canonical_name,
            "value": val if val is not None else 0,
            "value_text": str(val) if val is not None else "-",
            "unit": item.unit or "",
            "low": None,
            "high": None,
            "status": status,
            "flag": _STATUS_TO_FLAG.get(status, "normal"),
            "explain": item.explanation or "",
            "source": item.source or "",
        })
    counts = {
        "정상": sum(1 for it in items if it["status"] == "정상"),
        "주의": sum(1 for it in items if it["status"] == "주의"),
        "이상": sum(1 for it in items if it["status"] in ("이상", "응급")),
    }
    emergency = report.emergency_alerts[0] if report.emergency_alerts else None
    return {
        "items": items,
        "counts": counts,
        "emergency": emergency,
        "tracked": report.tracking_items,
        "summary": report.summary,
        "filename": filename,
        "analyzed_at": time.strftime("%Y-%m-%d"),
        "lifestyle_guide": [
            {
                "category": g.category,
                "lifestyle": g.lifestyle,
                "tracking": g.tracking,
                "department": g.department,
                "source": g.source,
            }
            for g in report.lifestyle_guide
        ],
    }


st.set_page_config(page_title="GoGoDoc — 검진 결과 AI 해석", page_icon="🫆", layout="wide")
inject_css(st)

settings = load_settings()
try:
    pool = init_db(settings)
except Exception:
    st.error("데이터베이스 연결에 실패했습니다. .env 설정을 확인하세요.")
    st.stop()

# ── 세션 기본값 ──────────────────────────────────────────
_defaults = dict(page="login", gender="male", age=40, analyzed=False,
                 emergency=False, item_filter="전체 항목", file=None, result=None,
                 user_name="", location="", user_id=0, selected_item_id=None,
                 recommended_hospitals=None, chat_open=False)
for k, v in _defaults.items():
    st.session_state.setdefault(k, v)


def go(page: str):
    st.session_state.page = page
    st.rerun()


# ══════════════════════════════════════════════════════════
# 공통 사이드바 헬퍼
# ══════════════════════════════════════════════════════════
_NAV_ITEMS = [
    ("dashboard", "대시보드"),
    ("analysis", "PDF 분석"),
    ("records", "검진 기록"),
    ("track", "추적 관찰"),
    ("settings", "설정"),
]


def _sidebar_brand():
    logo = ('<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" '
            'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
            '<path d="M3 12h4l2.5 7 4-14 2.5 7H21"/></svg>')
    st.markdown('<div style="display:flex;align-items:center;gap:11px;padding:4px 0">'
                '<div style="width:38px;height:38px;border-radius:11px;background:rgba(255,255,255,.10);'
                'display:flex;align-items:center;'
                f'justify-content:center">{logo}</div>'
                '<div><div style="font-size:17px;font-weight:800;line-height:1;color:#fff">GoGoDoc</div>'
                '<div style="font-size:11px;color:#B8C0CC;margin-top:4px">Health report interpreter</div></div></div>',
                unsafe_allow_html=True)


def _sidebar_nav(active: str):
    """클릭 가능한 사이드바 메뉴 — 활성 항목은 강조 HTML, 나머지는 Streamlit 버튼."""
    for key, label in _NAV_ITEMS:
        if key == active:
            st.markdown(
                f'<div style="display:flex;align-items:center;gap:11px;background:rgba(255,255,255,.10);'
                f'color:#fff;font-weight:760;font-size:14px;padding:11px 12px;'
                f'border-radius:11px;margin-bottom:4px;border-left:3px solid #fff">'
                f'<span>{label}</span></div>',
                unsafe_allow_html=True,
            )
        else:
            if st.button(label, key=f"nav_{key}", use_container_width=True):
                go(key)


def _sidebar_profile():
    name = st.session_state.get("user_name", "사용자")
    gender = st.session_state.get("gender", "male")
    age = st.session_state.get("age", 0)
    st.markdown(ui.sidebar_profile_html(name, gender, age), unsafe_allow_html=True)


def _sidebar_chat_toggle():
    open_now = bool(st.session_state.get("chat_open", False))
    st.markdown(
        '<div style="border-top:1px solid rgba(255,255,255,.10);margin:22px 0 14px"></div>',
        unsafe_allow_html=True,
    )
    label = "AI 챗봇 닫기" if open_now else "AI 챗봇 열기"
    if st.button(label, key="global_chat_toggle", use_container_width=True):
        st.session_state.chat_open = not open_now
        st.rerun()
    sub = "현재 화면 기반 상담 중" if open_now else "검진 결과와 병원 추천 상담"
    st.markdown(
        '<div style="background:rgba(255,255,255,.08);border:1px solid rgba(255,255,255,.08);'
        'border-radius:16px;padding:13px 14px;margin-top:8px;color:#fff">'
        '<div style="font-size:13px;font-weight:760">AI 보조 패널</div>'
        f'<div style="font-size:11px;color:#B8C0CC;line-height:1.55;margin-top:4px">{sub}</div></div>',
        unsafe_allow_html=True,
    )


def _sidebar_logout():
    if st.button("로그아웃", type="primary", use_container_width=True):
        st.session_state.clear()
        go("login")


def _chat_context() -> dict:
    page = st.session_state.get("page", "dashboard")
    result = st.session_state.get("result") or {}
    selected_id = st.session_state.get("selected_item_id")
    items = result.get("items") or []
    selected = next((it for it in items if it.get("id") == selected_id), None)

    if page == "analysis" and result:
        counts = result.get("counts") or {}
        return {
            "title": "분석 결과 컨텍스트",
            "body": f'{result.get("filename", "검진 결과지")} · 정상 {counts.get("정상", 0)} / 주의 {counts.get("주의", 0)} / 이상 {counts.get("이상", 0)}',
            "focus": f'{selected["name"]} {selected.get("value_text", selected.get("value", "-"))} {selected.get("unit", "")}' if selected else "전체 결과 요약",
        }
    if page == "track":
        return {"title": "추적 관찰 컨텍스트", "body": "검진별 주요 수치 변화와 다음 재검 일정", "focus": "추적 항목 변화량"}
    if page == "records":
        return {"title": "검진 기록 컨텍스트", "body": "저장된 과거 분석 결과 목록", "focus": "이전 결과 비교"}
    if page == "settings":
        location = st.session_state.get("location") or "거주지 미입력"
        return {"title": "설정 컨텍스트", "body": f'성별·나이·거주지 정보 ({location})', "focus": "개인화 기준"}
    return {"title": "대시보드 컨텍스트", "body": "최근 검진 요약과 관리 필요 항목", "focus": "건강 요약"}


def _render_ai_chat_panel():
    if not st.session_state.get("chat_open", False):
        return

    ctx = _chat_context()
    location = st.session_state.get("location") or "거주지 설정 필요"
    html = (
        '<aside class="gg-ai-panel">'
        '<div class="gg-ai-head">'
        '<div><div class="gg-ai-title">AI 챗봇</div>'
        '<div class="gg-ai-sub">현재 화면을 참조해 답변합니다</div></div>'
        '<div class="gg-ai-close">닫기는 사이드바 버튼</div></div>'
        '<div class="gg-ai-context">'
        f'<div class="gg-ai-context-label">{ctx["title"]}</div>'
        f'<div class="gg-ai-context-body">{ctx["body"]}</div>'
        f'<div class="gg-ai-context-focus">초점: {ctx["focus"]}</div></div>'
        '<div class="gg-ai-thread">'
        '<div class="gg-ai-row assistant"><div class="gg-ai-avatar">AI</div>'
        '<div class="gg-ai-bubble">검진 결과에서 관리가 필요한 항목을 기준으로 설명드릴게요. 궁금한 수치나 병원 추천을 물어보세요.</div></div>'
        '<div class="gg-ai-row user"><div class="gg-ai-user-bubble">LDL이 높으면 어디로 가야 하나요?</div></div>'
        '<div class="gg-ai-row assistant"><div class="gg-ai-avatar">AI</div>'
        '<div class="gg-ai-bubble"><b>추천 진료과</b><br>LDL 콜레스테롤 이상은 우선 내과 또는 가정의학과 상담이 적절합니다. 심혈관 위험 요인이 함께 있다면 심장내과 상담도 고려할 수 있습니다.'
        '<div class="gg-ai-reco"><div><b>추천 기준</b><br>LDL 156 mg/dL · 이상</div>'
        f'<div><b>지역</b><br>{location}</div></div>'
        '<button class="gg-ai-card-btn">챗봇에서 근처 병원 추천받기</button></div></div>'
        '</div>'
        '<div class="gg-ai-input"><span>검진 결과에 대해 질문해 보세요</span><button>전송</button></div>'
        '</aside>'
    )
    st.markdown(html, unsafe_allow_html=True)


def _page_shell_css():
    if st.session_state.get("chat_open", False):
        st.markdown(
            '<style>'
            'section.main,.stMain,[data-testid="stMain"]{margin-left:400px!important;'
            'width:calc(100% - 400px)!important;max-width:calc(100% - 400px)!important;'
            'transition:margin-left .18s ease,width .18s ease}'
            'section.main .block-container,.stMain .block-container,[data-testid="stMain"] .block-container{'
            'padding-left:2.8rem!important;max-width:1380px!important}'
            '@media (max-width:900px){section.main,.stMain,[data-testid="stMain"]{'
            'margin-left:0!important;width:100%!important;max-width:100%!important}}'
            '</style>',
            unsafe_allow_html=True,
        )


def _render_authenticated_sidebar(active: str):
    _page_shell_css()
    _render_ai_chat_panel()
    with st.sidebar:
        _sidebar_brand()
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
        _sidebar_nav(active)
        st.markdown('<div style="height:clamp(56px,28vh,250px)"></div>', unsafe_allow_html=True)
        _sidebar_chat_toggle()
        st.markdown('<div style="height:20px"></div>', unsafe_allow_html=True)
        _sidebar_profile()
        _sidebar_logout()


# ══════════════════════════════════════════════════════════
# 로그인 / 회원가입
# ══════════════════════════════════════════════════════════
def _auth_layout_css():
    st.markdown(
        "<style>.block-container{max-width:100%!important;"
        "padding:42px 56px 40px calc(26vw + 56px)!important}.stApp{background:#F5F7FB!important}"
        "@media (max-width:900px){.block-container{padding:22px 18px 28px 18px!important}}</style>",
        unsafe_allow_html=True,
    )


def render_login(pool):
    _auth_layout_css()
    st.markdown(ui.brand_panel_html(), unsafe_allow_html=True)
    _l, center, _r = st.columns([0.55, 0.9, 0.55], gap="large")
    with center:
        st.markdown('<div style="height:10vh"></div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown('<div class="gg-auth-eyebrow">GoGoDoc Workspace Access</div>'
                        '<div class="gg-auth-title">로그인</div>'
                        '<div class="gg-auth-desc">검진 기록과 해석 결과를 같은 기준으로 이어서 확인할 수 있도록 계정에 연결합니다.</div>'
                        '<div class="gg-auth-divider"></div>', unsafe_allow_html=True)
            st.text_input("이름", placeholder="홍길동", key="login_email")
            st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요", key="login_pw")
            st.checkbox("로그인 상태 유지", value=True)
            if st.button("로그인", type="primary", use_container_width=True):
                name = st.session_state.get("login_email", "")
                pw = st.session_state.get("login_pw", "")
                if not name or not pw:
                    st.warning("이름과 비밀번호를 입력하세요")
                else:
                    try:
                        user = login(pool, name, pw)
                        st.session_state.user_id = user["id"]
                        st.session_state.user_name = user["name"]
                        st.session_state.gender = user["sex"]
                        st.session_state.age = user["age"]
                        st.session_state.location = user.get("location", "")
                        go("dashboard")
                    except AuthError:
                        st.error("이름 또는 비밀번호가 올바르지 않습니다")
            st.markdown('<div class="gg-auth-footnote">계정이 없으신가요?</div>', unsafe_allow_html=True)
            if st.button("회원가입", use_container_width=True):
                go("signup")


def render_signup(pool):
    _auth_layout_css()
    st.markdown(ui.brand_panel_html(), unsafe_allow_html=True)
    left, right = st.columns([1.18, 0.92], gap="large")
    with left:
        st.markdown('<div class="gg-auth-aside">'
                    '<div class="gg-auth-aside-card">'
                    '<div class="gg-auth-aside-label">Profile Setup</div>'
                    '<div class="gg-auth-aside-title">초기 프로필 정보는 해석 기준과 추천 품질을 맞추는 데 사용됩니다</div>'
                    '<div class="gg-auth-aside-body">성별과 나이는 정상 범위 판단에 반영되고, 거주지는 챗봇 기반 병원 추천 정확도를 높이는 데 사용됩니다.</div>'
                    '</div>'
                    '<div class="gg-auth-aside-card">'
                    '<div class="gg-auth-aside-label">Privacy Principle</div>'
                    '<div class="gg-auth-checks">'
                    '<div class="gg-auth-check"><span class="gg-auth-check-dot">A</span>업로드 PDF는 세션 기준으로만 처리</div>'
                    '<div class="gg-auth-check"><span class="gg-auth-check-dot">B</span>기록 비교를 위한 분석 결과만 저장</div>'
                    '<div class="gg-auth-check"><span class="gg-auth-check-dot">C</span>병원 추천은 사용자 위치 기준으로만 보조</div>'
                    '</div></div></div>', unsafe_allow_html=True)
    with right:
        with st.container(border=True):
            st.markdown('<div class="gg-auth-eyebrow">Create Your Workspace</div>'
                        '<div class="gg-auth-title">회원가입</div>'
                        '<div class="gg-auth-desc">검진 결과를 개인 기준에 맞게 읽기 위해 최소한의 프로필 정보를 먼저 설정합니다.</div>'
                        '<div class="gg-auth-divider"></div>', unsafe_allow_html=True)
            st.text_input("이름", placeholder="홍길동", key="signup_name")
            st.text_input("이메일", placeholder="name@example.com")
            c1, c2 = st.columns(2)
            c1.text_input("비밀번호", type="password", placeholder="8자 이상", key="signup_pw")
            c2.text_input("비밀번호 확인", type="password", placeholder="다시 입력")
            c3, c4 = st.columns([1.4, 1])
            with c3:
                g = st.radio("성별", ["남성", "여성"], horizontal=True,
                             index=0 if st.session_state.gender == "male" else 1)
                st.session_state.gender = "male" if g == "남성" else "female"
            with c4:
                st.session_state.age = st.number_input("나이", 1, 120, st.session_state.age)
            st.text_input("거주지", placeholder="예) 서울특별시 강남구", key="signup_location")
            st.checkbox("서비스 이용약관 및 개인정보 처리방침에 동의합니다.", value=True)
            if st.button("가입하고 시작하기", type="primary", use_container_width=True):
                name = st.session_state.get("signup_name", "")
                pw = st.session_state.get("signup_pw", "")
                if not name or not pw:
                    st.warning("이름과 비밀번호를 입력하세요")
                else:
                    sex = st.session_state.gender
                    age = int(st.session_state.age)
                    location = st.session_state.get("signup_location", "")
                    try:
                        register(pool, name, pw, sex, age, location)
                        user = login(pool, name, pw)
                        st.session_state.user_id = user["id"]
                        st.session_state.user_name = user["name"]
                        st.session_state.gender = user["sex"]
                        st.session_state.age = user["age"]
                        st.session_state.location = user.get("location", "")
                        go("dashboard")
                    except DuplicateNameError:
                        st.error("이미 사용 중인 이름입니다")
            st.markdown('<div class="gg-auth-footnote">이미 계정이 있으신가요?</div>', unsafe_allow_html=True)
            if st.button("로그인", use_container_width=True, key="to_login"):
                go("login")


# ══════════════════════════════════════════════════════════
# 대시보드 헬퍼
# ══════════════════════════════════════════════════════════
def _extract_fbs_trend(history: list[dict]) -> dict:
    """이력에서 공복혈당 추이 추출 → fbs_chart_svg_html 포맷"""
    years, values = [], []
    for rec in reversed(history):
        for item in (rec.get("items_json") or []):
            if "공복혈당" in item.get("name", ""):
                val = item.get("value")
                if val and val != 0:
                    years.append(rec["analyzed_at"].strftime("%Y-%m"))
                    values.append(val)
                break
    return {"years": years, "values": values, "normal_max": 99}


def _history_to_records(history: list[dict]) -> list[dict]:
    """분석 이력 → records_html 포맷"""
    return [
        {
            "title": rec.get("filename") or "종합검진",
            "date": rec["analyzed_at"].strftime("%Y-%m-%d"),
            "center": "-",
            "normal": rec["normal_count"],
            "caution": rec["caution_count"],
            "abnormal": rec["abnormal_count"],
        }
        for rec in history
    ]


def _latest_to_tracked(latest: dict, prev: dict | None) -> list[dict]:
    """최신 결과의 추적 항목 → tracked_html 포맷"""
    tracking_names = latest.get("tracking_items") or []
    items_map = {it["name"]: it for it in (latest.get("items_json") or [])}
    prev_map = {it["name"]: it for it in (prev.get("items_json") or [])} if prev else {}

    tracked = []
    for name in tracking_names:
        it = items_map.get(name)
        if not it:
            continue
        val = it.get("value_text") or str(it.get("value", "-"))
        prev_it = prev_map.get(name)
        if prev_it and prev_it.get("value") is not None and it.get("value") is not None:
            diff = it["value"] - prev_it["value"]
            delta = f"+{diff:.1f}" if diff >= 0 else f"{diff:.1f}"
        else:
            delta = "-"
        low, high = it.get("low"), it.get("high")
        range_str = (f"{low}~{high}" if low and high else
                     f"{high} 이하" if high else
                     f"{low} 이상" if low else "-")
        tracked.append({
            "name": name,
            "value": val,
            "unit": it.get("unit", ""),
            "range": range_str,
            "status": it.get("status", "주의"),
            "delta": delta,
        })
    return tracked


def _load_record_to_session(rec: dict):
    """DB 레코드 → session_state.result 로드 (검진 기록 → 분석 뷰)"""
    items = rec.get("items_json") or []
    # flag 필드가 없는 레코드는 status에서 역산
    for it in items:
        if "flag" not in it:
            it["flag"] = _STATUS_TO_FLAG.get(it.get("status", "정상"), "normal")
    counts = {
        "정상": rec["normal_count"],
        "주의": rec["caution_count"],
        "이상": rec["abnormal_count"],
    }
    alerts = rec.get("emergency_alerts") or []
    st.session_state.result = {
        "items": items,
        "counts": counts,
        "emergency": alerts[0] if alerts else None,
        "tracked": rec.get("tracking_items") or [],
        "summary": "",
        "filename": rec.get("filename") or "종합검진",
        "record_id": rec.get("id"),
        "analyzed_at": rec["analyzed_at"].strftime("%Y-%m-%d"),
        "lifestyle_guide": [],
    }
    st.session_state.analyzed = True
    st.session_state.selected_item_id = None
    st.session_state.recommended_hospitals = None


@st.dialog("검진 기록을 삭제하시겠습니까?")
def _confirm_delete_record_dialog(pool, user_id: int, record_id: int, title: str, date_str: str):
    st.markdown(
        f'<div style="font-size:15px;font-weight:800;color:#1B2533">{title}</div>'
        f'<div style="font-size:12.5px;color:#8590A1;margin-top:4px">{date_str}</div>'
        '<div style="font-size:13px;color:#475467;line-height:1.65;margin-top:16px">'
        '삭제한 검진 기록은 복구할 수 없습니다. 정말 삭제하시겠습니까?</div>',
        unsafe_allow_html=True,
    )
    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    cancel_col, delete_col = st.columns(2)
    with cancel_col:
        if st.button("취소", use_container_width=True, key=f"cancel_delete_modal_{record_id}"):
            st.rerun()
    with delete_col:
        if st.button("삭제", type="primary", use_container_width=True,
                     key=f"confirm_delete_modal_{record_id}"):
            db_conn = get_conn(pool)
            try:
                deleted = delete_analysis(db_conn, user_id, record_id)
                db_conn.commit()
            except Exception as exc:
                db_conn.rollback()
                st.error(f"검진 기록 삭제 중 오류가 발생했습니다: {exc}")
                return
            finally:
                put_conn(pool, db_conn)

            current = st.session_state.get("result") or {}
            if current.get("record_id") == record_id:
                st.session_state.update(
                    analyzed=False,
                    result=None,
                    selected_item_id=None,
                    recommended_hospitals=None,
                )
            if deleted:
                st.session_state.record_delete_message = "검진 기록이 삭제되었습니다."
            else:
                st.session_state.record_delete_message = "삭제할 검진 기록을 찾지 못했습니다."
            st.rerun()


# ══════════════════════════════════════════════════════════
# 대시보드
# ══════════════════════════════════════════════════════════
def render_dashboard(pool):
    st.markdown("<style>.block-container{max-width:100%!important}</style>", unsafe_allow_html=True)
    _render_authenticated_sidebar("dashboard")

    user_id = st.session_state.get("user_id", 0)
    conn = get_conn(pool)
    try:
        latest = find_latest(conn, user_id)
        history = find_by_user(conn, user_id)
    finally:
        put_conn(pool, conn)

    user_name = st.session_state.get("user_name", "사용자")
    head, btn = st.columns([3, 1])
    with head:
        if latest:
            date_str = latest["analyzed_at"].strftime("%Y-%m-%d")
            sub = f"최근 검진일 {date_str} 기준, 건강 요약을 정리했어요."
        else:
            sub = "아직 검진 결과가 없어요. 검진 결과지를 업로드해 보세요."
        st.markdown(f'<h1 style="font-size:25px;font-weight:800;margin:0">안녕하세요, {user_name}님 👋</h1>'
                    f'<p style="font-size:14px;color:#7B8597;margin:8px 0 0">{sub}</p>',
                    unsafe_allow_html=True)
    with btn:
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        if st.button("＋ 새 검진 해석하기", type="primary", use_container_width=True):
            st.session_state.analyzed = False
            go("analysis")

    if not latest:
        st.info("검진 결과지 PDF를 업로드하면 AI 해석 결과가 여기에 표시됩니다.")
        return

    normal = latest["normal_count"]
    caution = latest["caution_count"]
    abnormal = latest["abnormal_count"]
    emergency = len(latest.get("emergency_alerts") or [])

    st.markdown(ui.kpi_cards_html(normal, caution, abnormal, emergency), unsafe_allow_html=True)
    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)

    fbs_trend = _extract_fbs_trend(history)
    prev = history[1] if len(history) >= 2 else None
    tracked = _latest_to_tracked(latest, prev)

    # 다음 검진 예정일 계산 (최신 분석일 + 90일)
    next_date = latest["analyzed_at"] + timedelta(days=90)
    next_date_label = next_date.strftime("%Y년 %m월 %d일") + " (약 3개월 후)"
    gcal_start = next_date.strftime("%Y%m%d")
    gcal_end = (next_date + timedelta(days=1)).strftime("%Y%m%d")
    gcal_url = (
        "https://calendar.google.com/calendar/render?action=TEMPLATE"
        "&text=%EA%B1%B4%EA%B0%95%EA%B2%80%EC%A7%84+%EC%98%88%EC%95%BD"
        f"&dates={gcal_start}/{gcal_end}"
        "&details=GoGoDoc+AI+%EC%B6%94%EC%B2%9C+%EC%9E%AC%EA%B2%80%EC%A7%84%EC%9D%BC"
    )

    left, right = st.columns([1.4, 1], gap="medium")
    with left:
        if len(fbs_trend["values"]) >= 2:
            st.markdown('<div class="gg-card" style="padding:22px 24px 8px">'
                        '<div style="font-size:15px;font-weight:800;color:#1B2533">공복혈당 추이</div>'
                        '<div style="font-size:12.5px;color:#8590A1;margin-top:4px">'
                        f'최근 {len(fbs_trend["values"])}회 검진 · 단위 mg/dL</div>',
                        unsafe_allow_html=True)
            st.markdown(ui.fbs_chart_svg_html(fbs_trend), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
    with right:
        if tracked:
            st.markdown(ui.tracked_html(tracked), unsafe_allow_html=True)
            if st.button("추적 항목 전체 보기 →", use_container_width=True, key="view_tracked"):
                go("track")
        st.markdown(ui.next_checkup_html(next_date_label, gcal_url), unsafe_allow_html=True)
        st.markdown(ui.disclaimer_html(), unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# 검진 기록 페이지
# ══════════════════════════════════════════════════════════
def render_records(pool):
    st.markdown(
        """
        <style>
        .block-container{max-width:100%!important}
        .gg-record-status-row{
            display:flex;gap:8px;align-items:center;justify-content:flex-end;padding-top:4px;
        }
        .gg-record-status{
            display:inline-flex;align-items:center;gap:6px;
            height:30px;padding:0 10px;border:1px solid #E3E8EF;border-radius:999px;
            background:#FFFFFF;color:#475467;font-size:12px;font-weight:700;
            box-shadow:0 1px 2px rgba(16,24,40,.04);
        }
        .gg-record-status b{color:#182230;font-size:12.5px;font-weight:800}
        .gg-record-dot{width:7px;height:7px;border-radius:50%;display:inline-block}
        div[data-testid="stHorizontalBlock"] > div:nth-child(4) .stButton > button{
            border-color:#F1B8B5!important;background:#FFF5F5!important;color:#B42318!important;
            font-weight:800!important;
        }
        div[data-testid="stHorizontalBlock"] > div:nth-child(4) .stButton > button:hover{
            border-color:#E5484D!important;background:#FEE4E2!important;color:#912018!important;
            box-shadow:0 5px 14px rgba(180,35,24,.14)!important;
        }
        div[role="dialog"] .stButton > button[kind="primary"]{
            background:#B42318!important;border:1px solid #B42318!important;color:#FFFFFF!important;
            box-shadow:0 8px 18px rgba(180,35,24,.22)!important;
        }
        div[role="dialog"] .stButton > button[kind="primary"]:hover{
            background:#912018!important;border-color:#912018!important;color:#FFFFFF!important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    _render_authenticated_sidebar("records")

    user_id = st.session_state.get("user_id", 0)
    conn = get_conn(pool)
    try:
        history = find_by_user(conn, user_id, limit=30)
    finally:
        put_conn(pool, conn)

    h_col, btn_col = st.columns([3, 1])
    with h_col:
        st.markdown('<h1 style="font-size:25px;font-weight:800;margin:0">검진 기록</h1>'
                    '<p style="font-size:14px;color:#7B8597;margin:8px 0 0">'
                    '모든 검진 결과를 확인하고 이전 분석 결과를 불러올 수 있어요.</p>',
                    unsafe_allow_html=True)
    with btn_col:
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        if st.button("＋ 새 검진 해석하기", type="primary", use_container_width=True):
            st.session_state.analyzed = False
            go("analysis")

    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
    if st.session_state.get("record_delete_message"):
        st.success(st.session_state.pop("record_delete_message"))

    if not history:
        st.info("검진 기록이 없어요. 검진 결과지 PDF를 업로드해 보세요.")
        return

    for rec in history:
        record_id = rec["id"]
        date_str = rec["analyzed_at"].strftime("%Y-%m-%d")
        title = rec.get("filename") or "종합검진"
        normal = rec["normal_count"]
        caution = rec["caution_count"]
        abnormal = rec["abnormal_count"]

        with st.container(border=True):
            c_info, c_pills, c_view, c_delete = st.columns([3, 2.3, 1, 0.8])
            with c_info:
                st.markdown(
                    f'<div style="font-size:15px;font-weight:700;color:#1B2533">{title}</div>'
                    f'<div style="font-size:12.5px;color:#8590A1;margin-top:3px">{date_str}</div>',
                    unsafe_allow_html=True,
                )
            with c_pills:
                st.markdown(
                    f'<div class="gg-record-status-row">'
                    f'<span class="gg-record-status"><i class="gg-record-dot" style="background:#3E7C59"></i>정상 <b>{normal}</b></span>'
                    f'<span class="gg-record-status"><i class="gg-record-dot" style="background:#B0893C"></i>주의 <b>{caution}</b></span>'
                    f'<span class="gg-record-status"><i class="gg-record-dot" style="background:#A14B45"></i>이상 <b>{abnormal}</b></span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with c_view:
                if st.button("결과 보기 →", key=f"rec_{record_id}", use_container_width=True):
                    _load_record_to_session(rec)
                    go("analysis")
            with c_delete:
                if st.button("삭제", key=f"delete_rec_{record_id}", use_container_width=True):
                    _confirm_delete_record_dialog(pool, user_id, record_id, title, date_str)


# ══════════════════════════════════════════════════════════
# 추적 관찰 페이지
# ══════════════════════════════════════════════════════════
def render_track(pool):
    st.markdown("<style>.block-container{max-width:100%!important}</style>", unsafe_allow_html=True)
    _render_authenticated_sidebar("track")

    user_id = st.session_state.get("user_id", 0)
    conn = get_conn(pool)
    try:
        history = find_by_user(conn, user_id, limit=20)
    finally:
        put_conn(pool, conn)

    st.markdown('<h1 style="font-size:25px;font-weight:800;margin:0">추적 관찰</h1>'
                '<p style="font-size:14px;color:#7B8597;margin:8px 0 20px">'
                '주요 수치의 검진별 변화를 추적합니다.</p>',
                unsafe_allow_html=True)

    if not history:
        st.info("아직 검진 기록이 없어요. 검진 결과지를 업로드해 보세요.")
        return

    latest = history[0]
    tracking_names = latest.get("tracking_items") or []

    if not tracking_names:
        st.info("추적 관찰 항목이 없어요. 검진 결과를 업로드하면 추적 항목이 자동으로 선택됩니다.")
        return

    cols = st.columns(2)
    for idx, item_name in enumerate(tracking_names):
        dates, values, unit_str = [], [], ""
        for rec in reversed(history):
            for it in (rec.get("items_json") or []):
                if it.get("name") == item_name:
                    val = it.get("value")
                    if val and val != 0:
                        dates.append(rec["analyzed_at"].strftime("%Y-%m"))
                        values.append(float(val))
                        unit_str = it.get("unit", "")
                    break

        with cols[idx % 2]:
            with st.container(border=True):
                st.markdown(
                    f'<div style="font-size:14px;font-weight:800;color:#15448A;margin-bottom:4px">'
                    f'📈 {item_name}'
                    f'<span style="font-size:12px;color:#9099A8;font-weight:500;margin-left:8px">'
                    f'{unit_str}</span></div>',
                    unsafe_allow_html=True,
                )
                if len(values) >= 2:
                    chart_data = dict(zip(dates, values))
                    st.line_chart(chart_data, height=160)
                    latest_val = values[-1]
                    prev_val = values[-2]
                    diff = latest_val - prev_val
                    diff_str = f"+{diff:.1f}" if diff >= 0 else f"{diff:.1f}"
                    diff_color = "#C0392B" if diff > 0 else "#1F8A5B"
                    st.markdown(
                        f'<div style="display:flex;align-items:baseline;gap:8px;margin-top:4px">'
                        f'<span style="font-size:22px;font-weight:800;color:#1B2533">{latest_val}</span>'
                        f'<span style="font-size:12px;color:#9099A8">{unit_str}</span>'
                        f'<span style="font-size:13px;font-weight:700;color:{diff_color};margin-left:auto">'
                        f'{diff_str}</span></div>',
                        unsafe_allow_html=True,
                    )
                elif len(values) == 1:
                    st.markdown(
                        f'<div style="font-size:22px;font-weight:800;color:#1B2533">{values[0]}'
                        f'<span style="font-size:12px;color:#9099A8;margin-left:4px">{unit_str}</span></div>'
                        f'<div style="font-size:12px;color:#A4ACBA;margin-top:6px">'
                        f'2회 이상 검진 기록이 있어야 추이를 확인할 수 있어요.</div>',
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown('<div style="font-size:13px;color:#A4ACBA">이 항목의 이력이 없어요.</div>',
                                unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# 설정 페이지
# ══════════════════════════════════════════════════════════
def render_settings(pool):
    st.markdown("<style>.block-container{max-width:100%!important}</style>", unsafe_allow_html=True)
    _render_authenticated_sidebar("settings")

    user_id = st.session_state.get("user_id", 0)
    user_name = st.session_state.get("user_name", "")

    st.markdown('<h1 style="font-size:25px;font-weight:800;margin:0">설정</h1>'
                '<p style="font-size:14px;color:#7B8597;margin:8px 0 24px">프로필 정보를 수정하세요.</p>',
                unsafe_allow_html=True)

    _l, mid, _r = st.columns([1, 2, 1])
    with mid:
        with st.container(border=True):
            st.markdown('<div style="font-size:16px;font-weight:800;margin-bottom:18px">👤 프로필 수정</div>',
                        unsafe_allow_html=True)

            st.text_input("이름", value=user_name, disabled=True,
                          help="이름은 변경할 수 없습니다.")

            g_idx = 0 if st.session_state.gender == "male" else 1
            g = st.radio("성별", ["남성", "여성"], horizontal=True, index=g_idx,
                         key="settings_gender")
            new_gender = "male" if g == "남성" else "female"

            new_age = st.number_input("나이", 1, 120, int(st.session_state.age),
                                      key="settings_age")
            new_location = st.text_input(
                "거주지", value=st.session_state.get("location", ""),
                placeholder="예) 서울특별시 강남구", key="settings_location",
                help="거주지는 병원 추천 기능에 사용됩니다.",
            )

            st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

            if st.button("저장", type="primary", use_container_width=True):
                if not user_id:
                    st.warning("로그인이 필요합니다.")
                else:
                    conn = get_conn(pool)
                    try:
                        update_user(conn, user_id,
                                    sex=new_gender,
                                    age=int(new_age),
                                    location=new_location.strip())
                        conn.commit()
                    finally:
                        put_conn(pool, conn)
                    st.session_state.gender = new_gender
                    st.session_state.age = int(new_age)
                    st.session_state.location = new_location.strip()
                    st.success("저장되었습니다.")


# ══════════════════════════════════════════════════════════
# 검진 결과 AI 해석 (업로드 → 파이프라인 → split 뷰)
# ══════════════════════════════════════════════════════════
def render_analysis(settings, pool):
    st.markdown("<style>.block-container{max-width:100%!important}</style>", unsafe_allow_html=True)
    _render_authenticated_sidebar("analysis")

    if not st.session_state.analyzed:
        _render_upload(settings, pool)
    else:
        _render_result()


def _render_upload(settings, pool):
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
                _run_and_store(uploaded, settings, pool)
            st.markdown('<div style="text-align:center;color:#A4ACBA;font-size:12px;margin:8px 0 6px">또는</div>',
                        unsafe_allow_html=True)
            if st.button("📄  샘플 결과지로 체험해보기", use_container_width=True):
                _run_and_store(None, settings, pool)

        st.markdown('<div style="height:6px"></div>', unsafe_allow_html=True)
        st.markdown(ui.feature_cards_html(), unsafe_allow_html=True)


def _run_and_store(file, settings, pool):
    if file is None:
        from pipeline import run_pipeline
        steps = ["검진 결과지 파싱 · 항목 추출", "정상 범위 매칭 (성별·나이 기준)",
                 "AI 근거 기반 해석 생성", "안전 검토 · 요약 정리"]
        with st.status("샘플 결과지를 분석하고 있어요", expanded=True) as status:
            for s in steps:
                st.write(f"✓ {s}")
                time.sleep(0.6)
            status.update(label="해석 완료", state="complete")
        res = run_pipeline(None, st.session_state.gender, st.session_state.age,
                           st.session_state.emergency)
        res.setdefault("filename", "샘플_결과지.pdf")
        res.setdefault("analyzed_at", time.strftime("%Y-%m-%d"))
        # flag 필드 보정
        for it in res.get("items", []):
            if "flag" not in it:
                it["flag"] = _STATUS_TO_FLAG.get(it.get("status", "정상"), "normal")
        st.session_state.result = res
        st.session_state.analyzed = True
        st.rerun()
        return

    try:
        validate_uploaded_pdf_metadata(
            filename=file.name,
            content_type=file.type,
            size_bytes=file.size,
        )
    except PdfValidationError as exc:
        st.error(exc.message)
        return

    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        tmp.write(file.getvalue())
        pdf_path = tmp.name

    try:
        try:
            validate_digital_pdf(pdf_path=pdf_path, filename=file.name, size_bytes=file.size)
        except PdfValidationError as exc:
            st.error(exc.message)
            return

        steps = ["검진 결과지 파싱 · 항목 추출", "정상 범위 매칭 (성별·나이 기준)",
                 "AI 근거 기반 해석 생성", "안전 검토 · 요약 정리"]
        with st.status("결과지를 분석하고 있어요", expanded=True) as status:
            for s in steps:
                st.write(f"✓ {s}")
            try:
                sex = Sex.MALE if st.session_state.gender == "male" else Sex.FEMALE
                profile = UserProfile(sex=sex, age=int(st.session_state.age))
                report = build_pipeline(settings).run(pdf_path, profile)
            except PdfValidationError as exc:
                st.error(exc.message)
                return
            except Exception as exc:
                st.error(f"분석 중 오류가 발생했습니다: {exc}")
                return
            status.update(label="해석 완료", state="complete")

        result = _report_to_result(report, filename=file.name)
        st.session_state.result = result

        user_id = st.session_state.get("user_id", 0)
        if user_id:
            db_conn = get_conn(pool)
            try:
                save_analysis(db_conn, user_id, file.name, result)
                db_conn.commit()
            finally:
                put_conn(pool, db_conn)

        st.session_state.analyzed = True
        st.rerun()
    finally:
        Path(pdf_path).unlink(missing_ok=True)


def _render_result():
    res = st.session_state.result
    if res is None:
        st.warning("분석 결과가 없습니다. 다시 업로드해 주세요.")
        st.session_state.update(analyzed=False)
        st.rerun()
        return

    counts = res["counts"]
    gender_short = "남" if st.session_state.gender == "male" else "여"
    user_name = st.session_state.get("user_name", "수검자")
    analyzed_at = res.get("analyzed_at", "")
    filename = res.get("filename", "종합검진_결과지.pdf")

    head, pills = st.columns([2, 1])
    with head:
        sub = ("응급 이상치가 포함되어 있어요. 아래 안내에 따라 즉시 의료기관에 내원하세요."
               if res["emergency"] else
               "정상 범위를 벗어난 항목이 있어요. 추적 관찰을 권장합니다."
               if counts["이상"] or counts["주의"] else "모든 항목이 정상 범위 안에 있어요.")
        st.markdown(f'<h2 style="font-size:23px;font-weight:800;margin:0">검진 결과 해석'
                    f'<span style="font-size:12px;font-weight:600;color:#5B6678;background:#F0F3F8;'
                    f'border:1px solid #E4E9F0;border-radius:8px;padding:4px 10px;margin-left:10px">'
                    f'📄 {filename}</span></h2>'
                    f'<div style="font-size:13.5px;color:#5B6678;margin-top:7px">{sub}</div>',
                    unsafe_allow_html=True)
    with pills:
        st.markdown(ui.summary_pills_html(counts["정상"], counts["주의"], counts["이상"]),
                    unsafe_allow_html=True)

    if res["emergency"]:
        st.markdown(ui.emergency_banner_html(res["emergency"]), unsafe_allow_html=True)

    if res.get("summary"):
        st.markdown(ui.summary_block_html(res["summary"]), unsafe_allow_html=True)

    f1, f2, f3 = st.columns([1.4, 1, 1])
    with f1:
        st.session_state.item_filter = st.radio(
            "필터", ["전체 항목", "주의·이상만"], horizontal=True, label_visibility="collapsed",
            index=0 if st.session_state.item_filter == "전체 항목" else 1)
    with f2:
        st.session_state.emergency = st.toggle("응급 시나리오 보기", value=st.session_state.emergency)
    with f3:
        if st.button("↻  다시 업로드", use_container_width=True):
            st.session_state.update(analyzed=False, file=None, emergency=False,
                                    selected_item_id=None, recommended_hospitals=None)
            st.rerun()

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)

    items = res["items"]
    shown = items if st.session_state.item_filter == "전체 항목" else [
        it for it in items if it["status"] != "정상"]

    left, right = st.columns([0.92, 1.08], gap="medium")

    # ── 왼쪽: 원본 검진 결과지 ──────────────────────────────
    with left:
        st.markdown('<div style="font-size:12.5px;font-weight:700;color:#9099A8;margin-bottom:9px">'
                    '📄 원본 검진 결과지</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(
                ui.report_table_top_html(gender_short, st.session_state.age,
                                         user_name=user_name, date_str=analyzed_at),
                unsafe_allow_html=True,
            )
            for it in items:
                selected = st.session_state.selected_item_id == it["id"]
                if _is_changeable(it["name"]):
                    c_row, c_btn = st.columns([10, 1])
                    with c_row:
                        st.markdown(ui.report_row_html(it, selected), unsafe_allow_html=True)
                    with c_btn:
                        btn_label = "✕" if selected else "›"
                        if st.button(btn_label, key=f"sel_{it['id']}"):
                            st.session_state.selected_item_id = None if selected else it["id"]
                            st.rerun()
                else:
                    st.markdown(ui.report_row_html(it, False), unsafe_allow_html=True)
            st.markdown(ui.report_table_note_html(), unsafe_allow_html=True)

    # ── 오른쪽: AI 해석 ──────────────────────────────────────
    with right:
        st.markdown('<div style="font-size:12.5px;font-weight:700;color:#15448A;margin-bottom:9px">'
                    '💡 AI 해석</div>', unsafe_allow_html=True)

        selected_id = st.session_state.get("selected_item_id")
        if selected_id:
            sel_item = next((it for it in items if it["id"] == selected_id), None)
            if sel_item:
                sel_guide = next(
                    (g for g in (res.get("lifestyle_guide") or [])
                     if g["category"] == sel_item["cat"]),
                    None,
                )
                st.markdown(ui.result_card_detail_html(sel_item, sel_guide), unsafe_allow_html=True)
                st.markdown('<div style="font-size:11.5px;color:#8590A1;text-align:center;margin-top:8px">'
                            '왼쪽 표에서 다른 항목을 선택하거나 아래 버튼으로 전체 보기로 돌아갈 수 있어요</div>',
                            unsafe_allow_html=True)
                if st.button("← 전체 항목 보기", use_container_width=True, key="back_to_all"):
                    st.session_state.selected_item_id = None
                    st.rerun()
        else:
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
            if res.get("lifestyle_guide"):
                st.markdown(ui.lifestyle_guide_html(res["lifestyle_guide"]), unsafe_allow_html=True)

            st.markdown(ui.chatbot_hospital_prompt_html(st.session_state.get("location", "")),
                        unsafe_allow_html=True)
            st.markdown(ui.disclaimer_html(), unsafe_allow_html=True)


def _render_hospital_recommendation(res: dict):
    """AI 해석 패널 하단 병원 추천 섹션."""
    location = st.session_state.get("location", "")

    st.markdown('<div style="height:10px"></div>', unsafe_allow_html=True)

    if not location:
        st.markdown(
            '<div style="background:#F6F9FD;border:1px solid #DCE8F5;border-radius:13px;'
            'padding:14px 16px;font-size:13px;color:#6B7588;line-height:1.6">'
            '🏥 <b style="color:#15448A">주변 병원 추천</b><br>'
            '<a href="#" style="color:#15448A;font-weight:700" onclick="void(0)">설정 페이지</a>에서 '
            '거주지를 입력하면 주변 병원을 추천받을 수 있어요.</div>',
            unsafe_allow_html=True,
        )
        if st.button("⚙ 설정에서 거주지 입력하기", use_container_width=True, key="goto_settings"):
            go("settings")
        return

    hospitals = st.session_state.get("recommended_hospitals")

    if hospitals is None:
        if st.button("🏥 주변 병원 추천 받기", use_container_width=True, key="get_hospitals"):
            from gogodoc.application.hospital_service import recommend_hospitals
            from gogodoc.infrastructure.llm.openai_client import OpenAILLM
            with st.spinner("주변 병원을 검색하고 있어요..."):
                try:
                    llm = OpenAILLM(settings)
                    hospitals = recommend_hospitals(res, location, llm, settings)
                    st.session_state.recommended_hospitals = hospitals
                    st.rerun()
                except Exception as exc:
                    st.error(f"병원 추천 중 오류가 발생했습니다: {exc}")
        return

    if not hospitals:
        st.info(f"'{location}' 지역에서 조건에 맞는 병원을 찾지 못했어요.")
        if st.button("다시 검색", use_container_width=True, key="retry_hospitals"):
            st.session_state.recommended_hospitals = None
            st.rerun()
        return

    st.markdown(
        f'<div style="font-size:14px;font-weight:800;color:#15448A;margin-bottom:10px">'
        f'🏥 추천 병원 ({location})</div>',
        unsafe_allow_html=True,
    )
    for h in hospitals:
        depts = ", ".join(h.get("departments") or []) or "-"
        tel = h.get("tel") or "-"
        url = h.get("url") or ""
        st.markdown(
            f'<div style="background:#fff;border:1px solid #E2E8F2;border-radius:13px;'
            f'padding:14px 16px;margin-bottom:8px">'
            f'<div style="font-size:14px;font-weight:700;color:#1B2533">{h["name"]}</div>'
            f'<div style="font-size:12.5px;color:#6B7588;margin-top:4px">{h.get("address","")}</div>'
            f'<div style="display:flex;gap:12px;margin-top:8px;font-size:12px;color:#8590A1">'
            f'<span>📞 {tel}</span>'
            f'<span>🩺 {depts}</span>'
            f'{"<span><a href=" + repr(url) + " target=_blank style=color:#15448A>홈페이지</a></span>" if url else ""}'
            f'</div></div>',
            unsafe_allow_html=True,
        )
    if st.button("↺ 다시 검색", use_container_width=True, key="refresh_hospitals"):
        st.session_state.recommended_hospitals = None
        st.rerun()


# ── 라우터 ───────────────────────────────────────────────
PAGES = {
    "login": lambda: render_login(pool),
    "signup": lambda: render_signup(pool),
    "dashboard": lambda: render_dashboard(pool),
    "analysis": lambda: render_analysis(settings, pool),
    "records": lambda: render_records(pool),
    "track": lambda: render_track(pool),
    "settings": lambda: render_settings(pool),
}
PAGES.get(st.session_state.page, lambda: render_login(pool))()
