# -*- coding: utf-8 -*-
"""GoGoDoc — 종합검진 결과 AI 해석 서비스 (Streamlit).

실행:  streamlit run app.py

페이지 라우팅(session_state.page):
  login → signup → dashboard → analysis → records → track → settings
"""
import re
import time
import tempfile
import os
from datetime import date, timedelta
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
from gogodoc.domain.reference import reference_dict

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


# Korean status → English flag (hospital_service 호환)
_STATUS_TO_FLAG = {
    "정상": "normal",
    "주의": "caution",
    "이상": "abnormal",
    "응급": "emergency",
}


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
    sex = st.session_state.get("gender", "male")
    age = int(st.session_state.get("age", 40) or 40)
    for item in report.items:
        status = _FLAG_STATUS.get(item.flag, "주의")
        val = item.value
        entry = reference_dict.lookup(item.canonical_name)
        selected_range = reference_dict.select_range(entry, sex, age) if entry else None
        low, high = selected_range if selected_range else (None, None)
        items.append({
            "id": item.canonical_name,
            "cat": _get_cat(item.canonical_name),
            "name": item.canonical_name,
            "value": val if val is not None else 0,
            "value_text": str(val) if val is not None else "-",
            "unit": item.unit or "",
            "low": low,
            "high": high,
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


def _fill_reference_ranges_for_ui(items: list[dict]) -> list[dict]:
    """화면 표시 전 성별·나이 기준 정상범위 보강."""
    sex = st.session_state.get("gender", "male")
    age = int(st.session_state.get("age", 40) or 40)
    for item in items:
        if item.get("low") is not None or item.get("high") is not None:
            continue
        entry = reference_dict.lookup(item.get("name", ""))
        selected_range = reference_dict.select_range(entry, sex, age) if entry else None
        if selected_range:
            item["low"], item["high"] = selected_range
    return items


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
    st.markdown(
        '<div style="display:flex;align-items:center;padding:2px 0 4px">'
        f'{ui.brand_lockup_html(icon_width=84, logo_width=224, gap=10)}'
        '</div>',
        unsafe_allow_html=True,
    )


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


_OVERLAY_CHAT_KEY = "overlay_chat_messages"
_HOSPITAL_RE = re.compile(r"병원|어디|진료과|어느\s*과|내원|어디로|우선|추천|위치")
_MD_BOLD = re.compile(r"\*\*(.+?)\*\*")
_MD_ITALIC = re.compile(r"\*(.+?)\*")


def _md_to_html(text: str) -> str:
    """마크다운 볼드·이탤릭을 HTML로 변환 후 개행 처리."""
    import html as _html_mod
    safe = _html_mod.escape(text)
    safe = _MD_BOLD.sub(r"<strong>\1</strong>", safe)
    safe = _MD_ITALIC.sub(r"<em>\1</em>", safe)
    return safe.replace("\n", "<br>")


def _maybe_add_hospitals(history: list, question: str, pool) -> list:
    """병원 관련 질문이면 HIRA API 결과를 후속 메시지로 추가."""
    if not _HOSPITAL_RE.search(question):
        return history

    result = st.session_state.get("result")
    location = (st.session_state.get("location") or "").strip()

    if not result:
        updated = list(history)
        updated.append({
            "role": "assistant",
            "content": "병원 추천을 위해 먼저 **검진 결과를 분석**하거나 기록에서 불러와 주세요.",
            "payload": {},
        })
        return updated

    if not location:
        updated = list(history)
        updated.append({
            "role": "assistant",
            "content": "병원 추천을 위해 **설정 페이지**에서 거주지를 먼저 입력해 주세요.",
            "payload": {},
        })
        return updated

    try:
        from gogodoc.application.hospital_service import recommend_hospitals
        from gogodoc.infrastructure.llm.openai_client import OpenAILLM
        llm = OpenAILLM(settings)
        hospitals = recommend_hospitals(result, location, llm, settings)
    except Exception as e:
        updated = list(history)
        updated.append({
            "role": "assistant",
            "content": f"병원 정보를 가져오는 중 오류가 발생했습니다: {e}",
            "payload": {},
        })
        return updated

    if not hospitals:
        updated = list(history)
        updated.append({
            "role": "assistant",
            "content": f"**{location}** 근처에서 해당 진료과 병원을 찾지 못했습니다.",
            "payload": {},
        })
        return updated

    lines = [f"📍 **{location} 근처 추천 병원**\n"]
    for h in hospitals:
        name = h.get("name", "")
        addr = h.get("address", "")
        tel = h.get("tel", "")
        depts = ", ".join(h.get("departments", [])[:3])
        line = f"**{name}**"
        if addr:
            line += f"\n{addr}"
        if tel:
            line += f" | ☎ {tel}"
        if depts:
            line += f"\n진료과: {depts}"
        lines.append(line)

    updated = list(history)
    updated.append({"role": "assistant", "content": "\n\n".join(lines), "payload": {}})
    return updated


_ECG_SVG = (
    '<svg width="18" height="14" viewBox="0 0 20 14" fill="none" xmlns="http://www.w3.org/2000/svg">'
    '<path d="M1 7h3l2-5 3 11 2.5-8L13 9.5H15" stroke="#15448A" stroke-width="1.7"'
    ' stroke-linecap="round" stroke-linejoin="round"/>'
    '<path d="M15 7h4" stroke="#15448A" stroke-width="1.7" stroke-linecap="round"/>'
    '</svg>'
)


def _render_ai_chat_panel(pool):
    """오버레이 AI 챗봇 패널 — HTML 프레임 + st.form으로 실제 LLM 연결."""
    if not st.session_state.get("chat_open", False):
        return

    ctx = _chat_context()
    st.session_state.setdefault(_OVERLAY_CHAT_KEY, [])
    messages = st.session_state[_OVERLAY_CHAT_KEY]

    # 채팅 히스토리 HTML
    if messages:
        thread_html = ""
        for msg in messages:
            content = _md_to_html(msg["content"])
            if msg["role"] == "user":
                thread_html += (
                    '<div class="gg-ai-row user">'
                    f'<div class="gg-ai-user-bubble">{content}</div></div>'
                )
            else:
                thread_html += (
                    f'<div class="gg-ai-row assistant">'
                    f'<div class="gg-ai-avatar">{_ECG_SVG}</div>'
                    f'<div class="gg-ai-bubble">{content}</div></div>'
                )
    else:
        thread_html = (
            f'<div class="gg-ai-row assistant">'
            f'<div class="gg-ai-avatar">{_ECG_SVG}</div>'
            '<div class="gg-ai-bubble">검진 결과에서 관리가 필요한 항목을 기준으로 '
            '설명드릴게요. 궁금한 수치나 병원 추천을 물어보세요.</div></div>'
        )

    panel_html = (
        '<aside class="gg-ai-panel">'
        # 헤더
        '<div class="gg-ai-head">'
        '<div>'
        '<div class="gg-ai-title">AI 챗봇</div>'
        '<div class="gg-ai-sub">현재 검진 결과를 참조해 답변합니다</div>'
        '</div>'
        '<span class="gg-ai-close">✕</span>'
        '</div>'
        # 컨텍스트 카드
        '<div class="gg-ai-context">'
        '<div class="gg-ai-context-label">현재 컨텍스트</div>'
        f'<div class="gg-ai-context-body">{ctx["body"]}</div>'
        f'<div class="gg-ai-context-focus">{ctx["focus"]}</div>'
        f'<div style="font-size:11px;color:#8CA3BF;margin-top:6px">'
        f'📍 거주지: {(st.session_state.get("location") or "미설정 — 설정 페이지에서 입력 필요")}'
        f'</div>'
        '</div>'
        # 채팅 스레드
        f'<div class="gg-ai-thread" id="gg-chat-thread">{thread_html}</div>'
        '</aside>'
        # form을 패널 하단에 고정하는 CSS
        '<style>'
        '[data-testid="stForm"]{'
        'position:fixed!important;left:21rem!important;bottom:0!important;'
        'width:400px!important;padding:14px 20px 18px!important;'
        'background:#fff!important;border-top:1px solid #E3E7EE!important;'
        'z-index:1001!important;margin:0!important;box-shadow:none!important}'
        '[data-testid="stForm"] [data-baseweb="input"] input{'
        'border-radius:10px!important;font-size:13.5px!important;'
        'border:1.5px solid #D7DEE8!important;padding:10px 14px!important}'
        '[data-testid="stFormSubmitButton"]>button{'
        'background:#15448A!important;color:#fff!important;'
        'border-radius:10px!important;font-weight:700!important;'
        'font-size:13px!important;padding:10px 16px!important;'
        'border:none!important;white-space:nowrap!important}'
        '#gg-chat-thread{padding-bottom:80px!important}'
        '</style>'
    )
    st.markdown(panel_html, unsafe_allow_html=True)

    # 실제 입력 처리 — st.form 사용 (CSS로 패널 하단에 고정됨)
    with st.form("gg_overlay_chat", clear_on_submit=True):
        col_input, col_btn = st.columns([5, 1])
        with col_input:
            user_input = st.text_input(
                "질문 입력",
                placeholder="검진 결과에 대해 질문해 보세요",
                label_visibility="collapsed",
            )
        with col_btn:
            submitted = st.form_submit_button("전송")

    if not (submitted and user_input and user_input.strip()):
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
                question=user_input.strip(),
                profile=profile,
                get_conn_fn=get_conn,
                put_conn_fn=put_conn,
            )
        except Exception:
            st.error("챗봇 답변 생성 중 오류가 발생했습니다.")
            return

    if payload is None:
        return

    history = append_chat_exchange(
        st.session_state[_OVERLAY_CHAT_KEY],
        user_input.strip(),
        payload,
    )
    history = _maybe_add_hospitals(history, user_input.strip(), pool)
    st.session_state[_OVERLAY_CHAT_KEY] = history
    st.rerun()


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


def _render_authenticated_sidebar(active: str, pool):
    _page_shell_css()
    _render_ai_chat_panel(pool)
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
        "<style>"
        ".stApp{background:#EBF0F8!important}"
        ".stApp>div,[data-testid='stAppViewContainer'],"
        "section.main,.stMain,[data-testid='stMain']{"
        "background:transparent!important;box-shadow:none!important}"
        ".block-container{max-width:100%!important;background:transparent!important;"
        "box-shadow:none!important;border:none!important;"
        "padding:20vh 0 40px calc(26vw + 80px)!important}"
        "[data-testid='stVerticalBlock'],[data-testid='stHorizontalBlock'],"
        "[data-testid='column'],.stColumn,.element-container{"
        "background:transparent!important;box-shadow:none!important;border:none!important}"
        "@media (max-width:900px){.block-container{padding:10vh 24px 40px 24px!important}}"
        "</style>",
        unsafe_allow_html=True,
    )


_NOBG_LOGO_B64: str = ""


def _load_nobg_logo() -> str:
    global _NOBG_LOGO_B64
    if not _NOBG_LOGO_B64:
        try:
            p = os.path.join(os.path.dirname(__file__), "assets", "logo_nobg.b64")
            with open(p, "r") as f:
                _NOBG_LOGO_B64 = f.read().strip()
        except Exception:
            _NOBG_LOGO_B64 = ""
    return _NOBG_LOGO_B64


_LOGIN_CSS = """
<style>
/* ── 로그인 폼 ── */

/* 폼 전체 최대 너비 제한 */
.block-container {
    max-width: 100% !important;
}

/* 로그인 화면 전역 카드형 래퍼 제거 */
[data-testid="stVerticalBlockBorderWrapper"] > div,
[data-testid="stVerticalBlock"],
[data-testid="stVerticalBlock"] > div,
[data-testid="stHorizontalBlock"],
[data-testid="stHorizontalBlock"] > div,
[data-testid="column"],
[data-testid="column"] > div,
.element-container {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
}

.gg-login-shell {
    width: 100%;
    max-width: 460px;
    margin: 0 auto;
}

.gg-login-kicker {
    font-size: 12px;
    font-weight: 800;
    letter-spacing: .08em;
    text-transform: uppercase;
    color: #64748B;
    margin-bottom: 14px;
}

.gg-login-title {
    font-size: 30px;
    font-weight: 800;
    color: #111827;
    letter-spacing: -.03em;
    margin: 0;
}

.gg-login-sub {
    font-size: 14px;
    line-height: 1.7;
    color: #667085;
    margin: 12px 0 28px;
}

.gg-login-footer {
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 8px;
    margin-top: 18px;
    font-size: 13.5px;
    color: #98A2B3;
}

/* 로그인 폼 래퍼 박스 제거 */
[data-testid="stForm"] {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    padding: 0 !important;
}
[data-testid="stForm"] > div,
[data-testid="stForm"] [data-testid="stVerticalBlock"],
[data-testid="stForm"] [data-testid="stVerticalBlock"] > div,
[data-testid="stForm"] [data-testid="stHorizontalBlock"],
[data-testid="stForm"] [data-testid="stHorizontalBlock"] > div,
[data-testid="stForm"] [data-testid="column"],
[data-testid="stForm"] [data-testid="column"] > div,
[data-testid="stForm"] .element-container {
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    border-radius: 0 !important;
}

/* 입력 필드: 흰 배경 + 연한 테두리 */
[data-testid="stTextInput"] input {
    border-radius: 12px !important;
    border: 1px solid #D7DEE8 !important;
    background: #FFFFFF !important;
    box-shadow: none !important;
    padding: 12px 16px !important;
    font-size: 15px !important;
    color: #182230 !important;
    height: 52px !important;
    transition: border-color .15s, box-shadow .15s !important;
}
[data-testid="stTextInput"] input:focus {
    border-color: #15448A !important;
    box-shadow: 0 0 0 3px rgba(21,68,138,.10) !important;
    outline: none !important;
}
[data-testid="stTextInput"] input::placeholder { color: #A0AEC0 !important; }

/* 레이블 */
[data-testid="stTextInput"] label {
    font-size: 13px !important;
    font-weight: 700 !important;
    color: #344054 !important;
    display: block !important;
    margin-bottom: 7px !important;
}

/* 로그인 버튼 */
[data-testid="stButton"]:has(button[kind="primary"]) button,
[data-testid="stFormSubmitButton"] button[kind="primary"] {
    border-radius: 12px !important;
    background: linear-gradient(135deg, #274777, #1C3559) !important;
    color: #fff !important;
    font-size: 16px !important;
    font-weight: 700 !important;
    letter-spacing: -.01em !important;
    height: 52px !important;
    border: none !important;
    box-shadow: 0 8px 18px rgba(28,53,89,.22) !important;
    transition: background .15s, box-shadow .15s !important;
}
[data-testid="stButton"]:has(button[kind="primary"]) button:hover,
[data-testid="stFormSubmitButton"] button[kind="primary"]:hover {
    background: linear-gradient(135deg, #22406B, #162E4D) !important;
    box-shadow: 0 10px 22px rgba(28,53,89,.28) !important;
}

/* 회원가입 버튼 → 링크 텍스트 */
[data-testid="stButton"]:has(button[kind="secondary"]) button {
    border: none !important;
    background: transparent !important;
    color: #15448A !important;
    font-size: 13px !important;
    font-weight: 700 !important;
    padding: 0 !important;
    box-shadow: none !important;
    text-decoration: underline !important;
    height: auto !important;
}

/* 체크박스 */
[data-testid="stCheckbox"] label {
    font-size: 13px !important;
    color: #475467 !important;
}
</style>
"""


def render_login(pool):
    _auth_layout_css()
    st.markdown(ui.brand_panel_html(), unsafe_allow_html=True)
    st.markdown(_LOGIN_CSS, unsafe_allow_html=True)

    submitted = False
    _left, center, _right = st.columns([0.9, 1.15, 1.05], gap="large")

    with center:
        st.markdown(
            '<div class="gg-login-shell">'
            '<div class="gg-login-kicker">Account Access</div>'
            '<h1 class="gg-login-title">로그인</h1>'
            '<p class="gg-login-sub">검진 기록과 해석 결과를 한곳에서 확인하고, 필요한 후속 관리 흐름까지 이어서 볼 수 있습니다.</p>',
            unsafe_allow_html=True,
        )

        with st.form("login_form"):
            st.text_input("이름", placeholder="홍길동", key="login_email")
            st.text_input("비밀번호", type="password", placeholder="비밀번호를 입력하세요", key="login_pw")

            chk_col, link_col = st.columns([1.2, 1])
            with chk_col:
                st.checkbox("로그인 상태 유지", value=False, key="login_remember")
            with link_col:
                st.markdown(
                    '<div style="text-align:right;padding-top:6px">'
                    '<span style="font-size:13px;color:#15448A;font-weight:700;cursor:pointer">비밀번호 찾기</span>'
                    '</div>',
                    unsafe_allow_html=True,
                )

            submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)

        st.markdown(
            '<div class="gg-login-footer"><span>계정이 없으신가요?</span></div>',
            unsafe_allow_html=True,
        )
        if st.button("회원가입", use_container_width=True, key="to_signup"):
            go("signup")
        st.markdown('</div>', unsafe_allow_html=True)

    if submitted:
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
def _pick_trend_item(history: list[dict]) -> tuple[str, str, float | None]:
    """이상·주의 항목 중 이력 데이터가 가장 많은 항목 선택.

    반환: (item_name, unit, normal_max)
    우선순위: 이상/응급 > 주의 > 정상, 동점이면 데이터 포인트 수 많은 쪽.
    """
    if not history:
        return "", "", None

    items = history[0].get("items_json") or []
    abnormal = [it for it in items if it.get("status") in ("이상", "응급")]
    caution  = [it for it in items if it.get("status") == "주의"]
    candidates = abnormal + caution or items  # 전부 정상이면 전체 후보

    best_name, best_unit, best_count = "", "", 0
    for it in candidates:
        name = it.get("name", "")
        count = sum(
            1 for rec in history
            for h_it in (rec.get("items_json") or [])
            if h_it.get("name") == name and h_it.get("value") and h_it.get("value") != 0
        )
        if count > best_count:
            best_count = count
            best_name = name
            best_unit = it.get("unit", "")

    best_item = next((it for it in items if it.get("name") == best_name), {})
    normal_max = best_item.get("high")
    return best_name, best_unit, normal_max


def _extract_item_trend(history: list[dict], item_name: str,
                        normal_max: float | None = None) -> dict:
    """이력에서 특정 항목 추이 추출 → trend_chart_svg_html 포맷."""
    years, values = [], []
    for rec in reversed(history):
        for item in (rec.get("items_json") or []):
            if item.get("name") == item_name:
                val = item.get("value")
                if val and val != 0:
                    years.append(rec["analyzed_at"].strftime("%Y-%m"))
                    values.append(val)
                break
    return {"years": years, "values": values, "normal_max": normal_max}


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
    _render_authenticated_sidebar("dashboard", pool)

    user_id = st.session_state.get("user_id", 0)
    conn = get_conn(pool)
    try:
        latest = find_latest(conn, user_id)
        history = find_by_user(conn, user_id)
    finally:
        put_conn(pool, conn)

    user_name = st.session_state.get("user_name", "사용자")
    if latest:
        date_str = latest["analyzed_at"].strftime("%Y-%m-%d")
        days_elapsed = (date.today() - latest["analyzed_at"].date()).days
        sub = f"최근 검진일 {date_str} 기준, 건강 요약을 정리했어요."
    else:
        days_elapsed = None
        sub = "아직 검진 결과가 없어요. 검진 결과지를 업로드해 보세요."

    head, btn = st.columns([3, 1])
    with head:
        st.markdown(ui.dashboard_hero_html(user_name, sub, days_elapsed), unsafe_allow_html=True)
    with btn:
        st.markdown('<div style="height:14px"></div>', unsafe_allow_html=True)
        if st.button("＋ 새 검진 해석하기", type="primary", use_container_width=True):
            st.session_state.analyzed = False
            go("analysis")

    if not latest:
        st.markdown(ui.dashboard_empty_html(), unsafe_allow_html=True)
        if _chat_test_ui_enabled():
            _render_chatbot_panel(settings, pool)
        return

    normal = latest["normal_count"]
    caution = latest["caution_count"]
    abnormal = latest["abnormal_count"]
    emergency = len(latest.get("emergency_alerts") or [])

    st.markdown(ui.kpi_cards_html(normal, caution, abnormal, emergency), unsafe_allow_html=True)
    st.markdown('<div style="height:18px"></div>', unsafe_allow_html=True)

    trend_name, trend_unit, trend_nmax = _pick_trend_item(history)
    item_trend = _extract_item_trend(history, trend_name, trend_nmax) if trend_name else {"years": [], "values": [], "normal_max": None}
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

    st.markdown('<div style="height:8px"></div>', unsafe_allow_html=True)
    left, right = st.columns([1.4, 1], gap="large")
    with left:
        if len(item_trend["values"]) >= 2:
            st.markdown(
                '<div class="gg-card" style="padding:22px 24px 8px">'
                '<div style="font-size:11px;font-weight:700;color:#94A3B8;letter-spacing:.5px;'
                'text-transform:uppercase;margin-bottom:6px">주요 수치 추이</div>'
                '<div style="font-size:22px;font-weight:800;color:#0D1117;letter-spacing:-.3px">'
                f'{trend_name} · {len(item_trend["values"])}회</div>'
                f'<div style="font-size:12px;color:#94A3B8;margin-top:3px">단위 {trend_unit}</div>',
                unsafe_allow_html=True,
            )
            st.markdown(ui.fbs_chart_svg_html(item_trend), unsafe_allow_html=True)
            st.markdown('</div>', unsafe_allow_html=True)
        if prev:
            st.markdown(ui.dashboard_comparison_html(latest, prev), unsafe_allow_html=True)
    with right:
        if tracked:
            st.markdown(ui.tracked_html(tracked), unsafe_allow_html=True)
            if st.button("추적 항목 전체 보기", use_container_width=True, key="view_tracked"):
                go("track")
        st.markdown(ui.next_checkup_html(next_date_label, gcal_url), unsafe_allow_html=True)
        st.markdown(ui.disclaimer_html(), unsafe_allow_html=True)

    if _chat_test_ui_enabled():
        _render_chatbot_panel(settings, pool)


# ══════════════════════════════════════════════════════════
# 검진 기록 페이지
# ══════════════════════════════════════════════════════════
def render_records(pool):
    st.markdown(
        """
        <style>
        .block-container{max-width:100%!important}
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
    _render_authenticated_sidebar("records", pool)

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
            c_info, c_bar, c_view, c_delete = st.columns([2.2, 3.2, 1, 0.8])
            with c_info:
                st.markdown(
                    f'<div style="font-size:15px;font-weight:700;color:#1B2533;line-height:1.3">{title}</div>'
                    f'<div style="font-size:12px;color:#94A3B8;margin-top:4px;font-weight:500">{date_str}</div>',
                    unsafe_allow_html=True,
                )
            with c_bar:
                total = normal + caution + abnormal or 1
                n_pct = round(normal  / total * 100)
                c_pct = round(caution / total * 100)
                a_pct = 100 - n_pct - c_pct
                st.markdown(
                    f'<div style="padding:4px 0">'
                    f'<div style="display:flex;height:7px;border-radius:99px;overflow:hidden;background:#F1F5F9;gap:2px">'
                    f'<div style="width:{n_pct}%;background:#059669;transition:width .3s"></div>'
                    f'<div style="width:{c_pct}%;background:#D97706;transition:width .3s"></div>'
                    f'<div style="width:{a_pct}%;background:#DC2626;transition:width .3s"></div>'
                    f'</div>'
                    f'<div style="display:flex;gap:14px;margin-top:7px;font-size:12px;font-weight:700;align-items:center">'
                    f'<span style="color:#059669">정상 {normal}</span>'
                    f'<span style="color:#D97706">주의 {caution}</span>'
                    f'<span style="color:#DC2626">이상 {abnormal}</span>'
                    f'<span style="color:#CBD5E1;font-size:11px;font-weight:500;margin-left:auto">전체 {total}항목</span>'
                    f'</div></div>',
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
    _render_authenticated_sidebar("track", pool)

    user_id = st.session_state.get("user_id", 0)
    conn = get_conn(pool)
    try:
        history = find_by_user(conn, user_id, limit=20)
    finally:
        put_conn(pool, conn)

    st.markdown(
        '<p style="font-size:11.5px;font-weight:700;color:#64748B;letter-spacing:.6px;'
        'text-transform:uppercase;margin:0 0 8px">추적 관찰</p>'
        '<h1 style="font-size:26px;font-weight:800;color:#0D1117;margin:0;letter-spacing:-.5px">'
        '주요 수치 변화 추적</h1>'
        '<p style="font-size:13.5px;color:#64748B;margin:8px 0 24px;font-weight:500">'
        '검진별 주요 수치를 추적하고 다음 재검 시점을 확인합니다.</p>',
        unsafe_allow_html=True,
    )

    if not history:
        st.markdown(
            '<div style="background:#fff;border:1px solid #E2E8F0;border-radius:14px;'
            'padding:40px 32px;text-align:center;color:#94A3B8;font-size:14px;margin-top:8px">'
            '아직 검진 기록이 없어요. 검진 결과지를 업로드해 보세요.</div>',
            unsafe_allow_html=True,
        )
        return

    latest = history[0]
    tracking_names = latest.get("tracking_items") or []

    if not tracking_names:
        st.markdown(
            '<div style="background:#fff;border:1px solid #E2E8F0;border-radius:14px;'
            'padding:40px 32px;text-align:center;color:#94A3B8;font-size:14px;margin-top:8px">'
            '추적 관찰 항목이 없어요. 검진 결과를 업로드하면 추적 항목이 자동으로 선택됩니다.</div>',
            unsafe_allow_html=True,
        )
        return

    latest_items_map = {it.get("name"): it for it in (latest.get("items_json") or [])}

    cols = st.columns(2, gap="medium")
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

        status = latest_items_map.get(item_name, {}).get("status", "주의")

        diff_str = "-"
        if len(values) >= 2:
            diff = values[-1] - values[-2]
            diff_str = f"+{diff:.1f}" if diff >= 0 else f"{diff:.1f}"

        with cols[idx % 2]:
            st.markdown(
                ui.track_item_card_html(item_name, dates, values, unit_str, status, diff_str, idx),
                unsafe_allow_html=True,
            )
            st.markdown('<div style="height:12px"></div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════
# 설정 페이지
# ══════════════════════════════════════════════════════════
def render_settings(pool):
    st.markdown("<style>.block-container{max-width:100%!important}</style>", unsafe_allow_html=True)
    _render_authenticated_sidebar("settings", pool)

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
    _render_authenticated_sidebar("analysis", pool)

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
        _save_result_for_user(
            pool,
            int(st.session_state.get("user_id") or 0),
            "sample_checkup.pdf",
            res,
        )
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
    gender_short = "남" if st.session_state.gender == "male" else "여"
    user_name = st.session_state.get("user_name", "수검자")
    analyzed_at = res.get("analyzed_at", "")
    filename = res.get("filename", "종합검진_결과지.pdf")

    head, pills = st.columns([1.55, 1.15])
    with head:
        st.markdown(f'<h2 style="font-size:41px;font-weight:850;margin:0;line-height:1.25;letter-spacing:-.6px">검진 결과 해석'
                    f'<span style="font-size:22px;font-weight:650;color:#5B6678;background:#F0F3F8;'
                    f'border:1px solid #E4E9F0;border-radius:10px;padding:7px 14px;margin-left:14px;vertical-align:middle">'
                    f'📄 {filename}</span></h2>',
                    unsafe_allow_html=True)
    with pills:
        st.markdown(ui.summary_pills_html(counts["정상"], counts["주의"], counts["이상"]),
                    unsafe_allow_html=True)

    if res["emergency"]:
        st.markdown(ui.emergency_banner_html(res["emergency"]), unsafe_allow_html=True)

    st.markdown(
        """
        <style>
        section.main .stButton > button {
            font-size: 15px !important;
            line-height: 1.25 !important;
            height: 56px !important;
            min-height: 56px !important;
            padding: 0 0.9rem !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            white-space: nowrap !important;
            overflow: hidden !important;
            text-overflow: ellipsis !important;
            word-break: keep-all !important;
        }
        section.main [data-testid="stRadio"] label,
        section.main [data-testid="stToggle"] label {
            font-size: 22px !important;
            line-height: 1.35 !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

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

    items = _fill_reference_ranges_for_ui(res["items"])
    left, right = st.columns([1.12, 1], gap="medium")

    # ── 왼쪽: 원본 검진 결과지 ──────────────────────────────
    with left:
        st.markdown('<div style="font-size:23px;font-weight:750;color:#9099A8;margin-bottom:16px;line-height:1.3">'
                    '📄 원본 검진 결과지</div>', unsafe_allow_html=True)
        with st.container(border=True):
            st.markdown(
                ui.report_table_top_html(gender_short, st.session_state.age,
                                         user_name=user_name, date_str=analyzed_at),
                unsafe_allow_html=True,
            )
            for it in items:
                selected = st.session_state.selected_item_id == it["id"]
                c_name, c_value, c_range = st.columns([1.45, 1.05, 1.15], gap="small")
                with c_name:
                    btn_label = f"✓ {it['name']}" if selected else it["name"]
                    if st.button(btn_label, key=f"sel_{it['id']}", use_container_width=True):
                        st.session_state.selected_item_id = None if selected else it["id"]
                        st.rerun()
                with c_value:
                    st.markdown(ui.report_value_cell_html(it), unsafe_allow_html=True)
                with c_range:
                    st.markdown(ui.report_range_cell_html(it), unsafe_allow_html=True)
            st.markdown(ui.report_table_note_html(), unsafe_allow_html=True)

    # ── 오른쪽: AI 해석 ──────────────────────────────────────
    with right:
        st.markdown('<div style="font-size:23px;font-weight:750;color:#15448A;margin-bottom:16px;line-height:1.3">'
                    '💡 AI 해석</div>', unsafe_allow_html=True)

        selected_id = st.session_state.get("selected_item_id")
        if selected_id:
            sel_item = next((it for it in items if it["id"] == selected_id), None)
            if sel_item:
                st.markdown(ui.item_definition_card_html(sel_item), unsafe_allow_html=True)
                st.markdown('<div style="font-size:12px;color:#8590A1;text-align:center;margin-top:8px;line-height:1.6;word-break:keep-all">'
                            '왼쪽 표에서 다른 항목을 선택하거나 아래 버튼으로 종합 가이드라인으로 돌아갈 수 있어요</div>',
                            unsafe_allow_html=True)
                if st.button("← 종합 가이드라인 보기", use_container_width=True, key="back_to_all"):
                    st.session_state.selected_item_id = None
                    st.rerun()
        else:
            st.markdown(ui.overall_guideline_html(res.get("summary", "")), unsafe_allow_html=True)


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
