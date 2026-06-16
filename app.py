# -*- coding: utf-8 -*-
"""GoGoDoc — 종합검진 결과 AI 해석 서비스 (Streamlit).

실행:  streamlit run streamlit_app/app.py

페이지 라우팅(session_state.page): login → signup → dashboard → analysis
- login/signup : 인증 화면 (좌측 브랜드 패널 + 폼)
- dashboard    : 건강 요약 / 추이 / 검진 기록 / 추적 관찰
- analysis     : PDF 업로드 → 4단계 파이프라인 → 원본/AI 해석 split 뷰
"""
import time
import tempfile
import os
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
)
from gogodoc.application.auth_service import login, register, AuthError, DuplicateNameError
from gogodoc.composition import build_pipeline, build_renderer, build_chat_ui_contract
from gogodoc.application.chat_ui_session import (
    append_chat_exchange,
    is_test_ui_enabled,
    profile_from_session,
    submit_latest_question,
)
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


# ── 어댑터 ───────────────────────────────────────────────
_FLAG_STATUS = {
    Flag.NORMAL: "정상",
    Flag.CAUTION: "주의",
    Flag.ABNORMAL: "이상",
    Flag.EMERGENCY: "응급",
    Flag.CHECK_NEEDED: "주의",
    Flag.UNKNOWN: "주의",
}


def _report_to_result(report) -> dict:
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
                 user_name="", location="", user_id=0)
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


def render_login(pool):
    _auth_layout_css()
    st.markdown(ui.brand_panel_html(), unsafe_allow_html=True)
    _l, mid, _r = st.columns([1.2, 1, 1.2])
    with mid:
        st.markdown('<div style="height:14vh"></div>', unsafe_allow_html=True)
        st.markdown('<h2 style="font-size:27px;font-weight:800;margin:0">로그인</h2>'
                    '<p style="font-size:14px;color:#7B8597;margin:9px 0 18px">'
                    '검진 기록과 해석 결과를 한곳에서 관리하세요.</p>', unsafe_allow_html=True)
        st.text_input("이름", placeholder="홍길동", key="login_email")
        st.text_input("비밀번호", type="password", placeholder="••••••••", key="login_pw")
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
        st.markdown('<div style="text-align:center;font-size:13.5px;color:#7B8597;margin-top:16px">'
                    '계정이 없으신가요?</div>', unsafe_allow_html=True)
        if st.button("회원가입", use_container_width=True):
            go("signup")


def render_signup(pool):
    _auth_layout_css()
    st.markdown(ui.brand_panel_html(), unsafe_allow_html=True)
    _l, mid, _r = st.columns([0.7, 1, 0.7])
    with mid:
        st.markdown('<div style="height:5vh"></div>', unsafe_allow_html=True)
        st.markdown('<h2 style="font-size:27px;font-weight:800;margin:0">회원가입</h2>'
                    '<p style="font-size:14px;color:#7B8597;margin:9px 0 14px">'
                    '성별·나이는 정상 범위 판정 기준으로 사용됩니다.</p>', unsafe_allow_html=True)
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
        st.markdown('<div style="text-align:center;font-size:13.5px;color:#7B8597;margin-top:14px">'
                    '이미 계정이 있으신가요?</div>', unsafe_allow_html=True)
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


def _get_chat_ui_contract(settings):
    """F-007 챗봇 UI 계약을 세션 단위로 재사용한다."""
    key = "_f007_chat_ui_contract"
    if key not in st.session_state:
        st.session_state[key] = build_chat_ui_contract(settings)
    return st.session_state[key]


def _render_chat_debug(payload: dict):
    """챗봇 응답 payload의 테스트용 메타데이터를 표시한다."""
    meta = {
        "scope_flag": payload.get("scope_flag"),
        "routed": payload.get("routed"),
        "latest_analysis_checked": payload.get("latest_analysis_checked"),
        "has_latest_analysis": payload.get("has_latest_analysis"),
        "analysis_id": payload.get("analysis_id"),
        "analysis_filename": payload.get("analysis_filename"),
        "context_item_names": payload.get("context_item_names") or [],
        "sources": payload.get("sources") or [],
    }
    st.caption(
        f"scope={meta['scope_flag']} · routed={meta['routed']} · "
        f"latest={meta['has_latest_analysis']}"
    )
    with st.expander("응답 메타데이터", expanded=False):
        st.json(meta)


def _render_chatbot_panel(settings, pool):
    """대시보드용 F-007 챗봇 수동 테스트 패널."""
    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)
    st.subheader("검진 결과 챗봇 테스트")
    st.caption("현재 로그인 사용자와 최신 검진 결과를 기준으로 F-007 답변 서비스를 직접 확인합니다.")

    history_key = "f007_chat_messages"
    st.session_state.setdefault(history_key, [])

    with st.container(border=True):
        top_left, top_right = st.columns([3, 1])
        with top_left:
            st.caption("허용 질문은 최신 검진 결과를 조회하고, 차단 질문은 전문의 상담 안내로 라우팅됩니다.")
        with top_right:
            if st.button("대화 초기화", use_container_width=True, key="f007_chat_reset"):
                st.session_state[history_key] = []
                st.rerun()

        for message in st.session_state[history_key]:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                if message["role"] == "assistant" and message.get("payload"):
                    _render_chat_debug(message["payload"])

        c1, c2, c3 = st.columns(3)
        sample_prompt = None
        if c1.button("BMI 관리 질문", use_container_width=True):
            sample_prompt = "BMI가 높으면 어떻게 관리해요?"
        if c2.button("ALT 의미 질문", use_container_width=True):
            sample_prompt = "ALT 수치가 높으면 어떤 의미예요?"
        if c3.button("약물 질문 차단 확인", use_container_width=True):
            sample_prompt = "이 수치면 무슨 약을 먹어야 하나요?"

        typed_prompt = st.chat_input("검진 결과에 대해 질문해보세요", key="f007_chat_input")
        prompt = sample_prompt or typed_prompt
        if not prompt:
            return

        user_id = int(st.session_state.get("user_id") or 0)
        profile = profile_from_session(
            st.session_state.get("gender"),
            st.session_state.get("age"),
        )
        contract = _get_chat_ui_contract(settings)

        with st.spinner("챗봇 답변을 생성하고 있어요"):
            try:
                payload = submit_latest_question(
                    contract=contract,
                    pool=pool,
                    user_id=user_id,
                    question=prompt,
                    profile=profile,
                    get_conn_fn=get_conn,
                    put_conn_fn=put_conn,
                )
            except Exception:
                st.error("챗봇 답변 생성 중 오류가 발생했습니다. 설정과 최신 검진 결과를 확인하세요.")
                return

        if payload is None:
            return

        st.session_state[history_key] = append_chat_exchange(
            st.session_state[history_key],
            prompt.strip(),
            payload,
        )
        st.rerun()


def _chat_test_ui_enabled() -> bool:
    """제품 화면 기본값에서 테스트용 챗봇 UI를 숨긴다."""
    return is_test_ui_enabled(os.getenv("ENABLE_F007_CHAT_TEST_UI"))


def _save_result_for_user(pool, user_id: int, filename: str, result: dict):
    """분석 결과를 로그인 사용자 이력으로 저장한다."""
    if not user_id:
        return
    db_conn = get_conn(pool)
    try:
        save_analysis(db_conn, user_id, filename, result)
        db_conn.commit()
    finally:
        put_conn(pool, db_conn)


# ══════════════════════════════════════════════════════════
# 대시보드
# ══════════════════════════════════════════════════════════
def render_dashboard(pool):
    st.markdown("<style>.block-container{max-width:100%!important}</style>", unsafe_allow_html=True)
    with st.sidebar:
        _sidebar_brand()
        st.markdown('<div style="height:16px"></div>', unsafe_allow_html=True)
        st.markdown(ui.sidebar_nav_html("dashboard"), unsafe_allow_html=True)
        st.markdown('<div style="height:40vh"></div>', unsafe_allow_html=True)
        st.markdown(ui.sidebar_profile_html(), unsafe_allow_html=True)
        if st.button("로그아웃", use_container_width=True):
            st.session_state.clear()
            go("login")

    # DB에서 실제 데이터 로드
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
        if _chat_test_ui_enabled():
            _render_chatbot_panel(settings, pool)
        return

    normal = latest["normal_count"]
    caution = latest["caution_count"]
    abnormal = latest["abnormal_count"]
    emergency = len(latest.get("emergency_alerts") or [])

    st.markdown(ui.kpi_cards_html(normal, caution, abnormal, emergency), unsafe_allow_html=True)
    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)

    fbs_trend = _extract_fbs_trend(history)
    records = _history_to_records(history)
    prev = history[1] if len(history) >= 2 else None
    tracked = _latest_to_tracked(latest, prev)

    left, right = st.columns([1.4, 1], gap="medium")
    with left:
        if len(fbs_trend["values"]) >= 2:
            st.markdown('<div class="gg-card" style="padding:22px 24px 8px">'
                        '<div style="font-size:15px;font-weight:800">공복혈당 추이</div>'
                        '<div style="font-size:12.5px;color:#8590A1;margin-top:4px">'
                        f'최근 {len(fbs_trend["values"])}회 검진 · 단위 mg/dL</div>',
                        unsafe_allow_html=True)
            st.markdown(ui.fbs_chart_svg_html(fbs_trend), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        st.markdown(ui.records_html(records), unsafe_allow_html=True)
    with right:
        if tracked:
            st.markdown(ui.tracked_html(tracked), unsafe_allow_html=True)
        st.markdown(ui.next_checkup_html(), unsafe_allow_html=True)
        st.markdown(ui.disclaimer_html(), unsafe_allow_html=True)

    if _chat_test_ui_enabled():
        _render_chatbot_panel(settings, pool)


# ══════════════════════════════════════════════════════════
# 검진 결과 AI 해석 (업로드 → 파이프라인 → split 뷰)
# ══════════════════════════════════════════════════════════
def render_analysis(settings, pool):
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
        # 샘플 체험 모드 — 기존 더미 파이프라인 유지
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
        st.session_state.result = res
        _save_result_for_user(
            pool,
            int(st.session_state.get("user_id") or 0),
            "sample_checkup.pdf",
            res,
        )
        st.session_state.analyzed = True
        st.rerun()
        return

    # 실제 PDF 파이프라인
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

        result = _report_to_result(report)
        st.session_state.result = result

        # 분석 결과 DB 저장
        _save_result_for_user(
            pool,
            int(st.session_state.get("user_id") or 0),
            file.name,
            result,
        )

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

    # AI 종합 요약 (직장인용)
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
        # 카테고리별 생활 가이드 (근거 기반)
        if res.get("lifestyle_guide"):
            st.markdown(ui.lifestyle_guide_html(res["lifestyle_guide"]), unsafe_allow_html=True)
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
PAGES = {"login": lambda: render_login(pool),
         "signup": lambda: render_signup(pool),
         "dashboard": lambda: render_dashboard(pool),
         "analysis": lambda: render_analysis(settings, pool)}
PAGES.get(st.session_state.page, lambda: render_login(pool))()
