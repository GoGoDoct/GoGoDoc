# -*- coding: utf-8 -*-
"""GoGoDoc 전역 스타일 (딥블루 / Pretendard).

Streamlit 기본 크롬을 숨기고, 위젯을 브랜드 톤으로 재정의한다.
app.py 최상단에서 inject_css(st) 한 번만 호출하면 된다.
"""

CSS = """
<style>
@import url('https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.css');

/* ── 전역 ─────────────────────────────────────────── */
html, body, [class*="css"], .stApp, button, input, textarea, select {
    font-family: 'Pretendard', system-ui, -apple-system, sans-serif !important;
    font-size: 16px;
}
.stApp { background: #F1F4F8; color: #111827; }

/* Streamlit 기본 크롬 숨기기 */
#MainMenu, header[data-testid="stHeader"], footer { visibility: hidden; height: 0; }
[data-testid="stToolbar"], [data-testid="stDecoration"] { display: none; }

/* ── 고정 화면 레이아웃 (스크롤은 콘텐츠 영역 내부로) ── */
html, body { height: 100vh !important; overflow: hidden !important; }
.stApp   { height: 100vh !important; overflow: hidden !important; }

/* 메인 콘텐츠 — 자체 스크롤바 */
section.main {
    height: 100vh !important;
    overflow-y: auto !important;
    overflow-x: hidden !important;
}
/* 사이드바 — 고정 높이, 내용이 넘치면 자체 스크롤 */
[data-testid="stSidebar"] {
    height: 100vh !important;
    overflow-y: auto !important;
}

/* 메인 스크롤바 스타일 */
section.main::-webkit-scrollbar { width: 7px; }
section.main::-webkit-scrollbar-track { background: #F1F4F8; }
section.main::-webkit-scrollbar-thumb {
    background: #B8C2D0; border-radius: 99px; border: 2px solid #F1F4F8;
}
section.main::-webkit-scrollbar-thumb:hover { background: #9CAABB; }

/* 사이드바 스크롤바 */
[data-testid="stSidebar"]::-webkit-scrollbar { width: 4px; }
[data-testid="stSidebar"]::-webkit-scrollbar-thumb {
    background: #DCE3EC; border-radius: 99px;
}

/* 본문 여백 */
.block-container { padding: 2rem 2.8rem 3rem; max-width: 1380px; }

/* ── 인증 화면 ─────────────────────────────────────── */
.gg-auth-main {
    min-height: 100vh;
    background:
        radial-gradient(circle at 82% 18%, rgba(35, 76, 125, .08), transparent 22%),
        linear-gradient(180deg, #F5F7FB 0%, #EEF2F7 100%);
}
.gg-auth-brand-panel { display: flex; }
.gg-auth-grid {
    display: grid;
    grid-template-columns: minmax(420px, 560px) minmax(360px, 460px);
    justify-content: center;
    align-items: center;
    gap: 56px;
    min-height: 100vh;
    padding: 40px 56px 40px calc(26vw + 56px);
}
.gg-auth-card {
    background: rgba(255,255,255,.92);
    border: 1px solid #E2E8F0;
    border-radius: 28px;
    box-shadow: 0 18px 50px rgba(17,24,39,.08);
    padding: 38px 36px 32px;
    backdrop-filter: blur(6px);
}
.gg-auth-eyebrow {
    display: inline-flex;
    align-items: center;
    gap: 8px;
    padding: 7px 12px;
    border-radius: 999px;
    background: #F3F6FA;
    border: 1px solid #E3E8EF;
    color: #425466;
    font-size: 12px;
    font-weight: 800;
    letter-spacing: .2px;
}
.gg-auth-title {
    margin: 18px 0 0;
    color: #111827;
    font-size: 31px;
    font-weight: 800;
    letter-spacing: -.7px;
}
.gg-auth-desc {
    margin: 12px 0 0;
    color: #4B5565;
    font-size: 14px;
    line-height: 1.75;
}
.gg-auth-divider {
    height: 1px;
    background: linear-gradient(90deg, #E3E8EF, rgba(227,232,239,0));
    margin: 24px 0 18px;
}
.gg-auth-footnote {
    margin-top: 16px;
    text-align: center;
    font-size: 13.5px;
    color: #667085;
}
.gg-auth-aside {
    display: flex;
    flex-direction: column;
    gap: 18px;
}
.gg-auth-aside-card {
    background: rgba(255,255,255,.72);
    border: 1px solid #E3E8EF;
    border-radius: 24px;
    padding: 22px 24px;
    box-shadow: 0 12px 28px rgba(17,24,39,.05);
}
.gg-auth-aside-label {
    color: #667085;
    font-size: 11px;
    font-weight: 800;
    letter-spacing: .5px;
    text-transform: uppercase;
}
.gg-auth-aside-title {
    margin-top: 10px;
    color: #182230;
    font-size: 22px;
    font-weight: 800;
    line-height: 1.4;
    letter-spacing: -.4px;
}
.gg-auth-aside-body {
    margin-top: 12px;
    color: #475467;
    font-size: 14px;
    line-height: 1.75;
}
.gg-auth-checks {
    display: grid;
    gap: 12px;
    margin-top: 18px;
}
.gg-auth-check {
    display: flex;
    align-items: center;
    gap: 12px;
    color: #344054;
    font-size: 13.5px;
    font-weight: 700;
}
.gg-auth-check-dot {
    width: 24px;
    height: 24px;
    border-radius: 999px;
    background: #EAF0F7;
    border: 1px solid #D5DEEA;
    color: #173557;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 800;
    flex: none;
}

/* ── 사이드바 ─────────────────────────────────────── */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #172335 0%, #101927 100%);
    border-right: 1px solid rgba(255,255,255,.08);
}
[data-testid="stSidebar"] .block-container { padding-top: 1.6rem; }

/* 사이드바 nav 버튼 */
[data-testid="stSidebarContent"] .stButton > button {
    border: none !important; background: transparent !important;
    color: #B8C0CC !important; text-align: left !important;
    justify-content: flex-start !important; padding: 10px 12px !important;
    border-radius: 10px !important; font-size: 14px !important;
    font-weight: 700 !important; box-shadow: none !important; margin-bottom: 2px !important;
    transition: all .12s !important;
}
[data-testid="stSidebarContent"] .stButton > button:hover {
    background: rgba(255,255,255,.08) !important; color: #FFFFFF !important; border: none !important;
}
[data-testid="stSidebarContent"] .stButton > button[kind="primary"] {
    background: rgba(255,255,255,.10) !important;
    color: #fff !important; box-shadow: none !important;
    border-radius: 10px !important;
}

/* ── 버튼 ─────────────────────────────────────────── */
.stButton > button {
    border-radius: 12px; font-weight: 700; font-size: 15px;
    border: 1px solid #D7DEE8; background: #fff; color: #253044;
    padding: 0.6rem 1.1rem; transition: all .15s; box-shadow: none;
}
.stButton > button:hover {
    border-color: #B8C2D0; background: #F8FAFC; color: #173557;
    transform: translateY(-1px); box-shadow: 0 4px 12px rgba(27,37,51,.08);
}
.stButton > button[kind="primary"] {
    background: linear-gradient(135deg, #234C7D, #173557); border: none; color: #fff;
    box-shadow: 0 6px 18px rgba(23,53,87,.24);
}
.stButton > button[kind="primary"]:hover {
    background: linear-gradient(135deg, #1F456F, #142D4A); color: #fff;
    box-shadow: 0 8px 22px rgba(23,53,87,.32); transform: translateY(-1px);
}

/* 다운로드/링크 버튼 */
.stDownloadButton > button { border-radius: 12px; font-weight: 700; }

/* ── 입력 위젯 ────────────────────────────────────── */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
    border-radius: 12px !important; border: 1.5px solid #DCE3EC !important;
    background: #FBFCFE !important; color: #182230 !important; height: 50px; font-size: 15px;
    transition: all .15s !important;
}
[data-testid="stTextInput"] input::placeholder, [data-testid="stNumberInput"] input::placeholder {
    color: #98A2B3 !important;
    opacity: 1 !important;
}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {
    border-color: #15448A !important; box-shadow: 0 0 0 3px rgba(21,68,138,.10) !important;
    background: #fff !important;
}
[data-testid="stWidgetLabel"] p { font-size: 14px !important; font-weight: 700; color: #344054; }
[data-testid="stSidebar"] [data-testid="stWidgetLabel"] p { color: #B8C0CC !important; }
[data-testid="stSidebar"] [data-testid="stRadio"] label,
[data-testid="stSidebar"] [data-testid="stNumberInput"] label { color: #D8DEE8 !important; }

/* 라디오 */
[data-testid="stRadio"] [role="radiogroup"] { gap: 8px; }
[data-testid="stRadio"] label { font-size: 14px !important; }

/* 파일 업로더 */
[data-testid="stFileUploader"] section {
    border: 2px dashed #C6D3E4; border-radius: 16px; background: #FAFCFE; padding: 22px;
    transition: border-color .15s;
}
[data-testid="stFileUploader"] section:hover { border-color: #15448A; background: #F4F8FF; }

/* 파일 업로더 한글화 */
[data-testid="stFileUploaderDropzone"] {
    flex-direction: column; align-items: center; text-align: center; gap: 10px; padding: 34px 18px;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
    display: flex; flex-direction: column; align-items: center;
}
[data-testid="stFileUploaderDropzoneInstructions"] span { font-size: 0; }
[data-testid="stFileUploaderDropzoneInstructions"] span::after {
    content: "결과지 PDF를 끌어다 놓으세요"; font-size: 16px; font-weight: 700; color: #3C4656;
}
[data-testid="stFileUploaderDropzoneInstructions"] small { font-size: 0; }
[data-testid="stFileUploaderDropzoneInstructions"] small::after {
    content: "또는 파일을 선택해 업로드 · 최대 200MB · PDF"; font-size: 13px; color: #9099A8;
}
[data-testid="stFileUploaderDropzone"] button { font-size: 0 !important; }
[data-testid="stFileUploaderDropzone"] button::after { content: "파일 선택"; font-size: 15px; font-weight: 700; }

/* 탭 */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #E8EDF5; padding: 4px; border-radius: 12px; }
.stTabs [data-baseweb="tab"] { height: 38px; border-radius: 9px; padding: 0 18px; font-weight: 700; font-size: 14px; color: #7B8597; }
.stTabs [aria-selected="true"] { background: #fff; color: #15448A; box-shadow: 0 2px 8px rgba(27,37,51,.10); }

/* details 쉬운 설명 */
details.gg-details { margin-top: 4px; }
details.gg-details > summary {
    list-style: none; cursor: pointer; padding: 11px 20px; border-top: 1px solid #F2F5F9;
    font-size: 13.5px; font-weight: 700; color: #15448A; letter-spacing: -.2px;
}
details.gg-details > summary::-webkit-details-marker { display: none; }
details.gg-details[open] > summary { color: #5B6678; }

/* ── 재사용 카드/요소 클래스 ──────────────────────── */
.gg-card {
    background: #fff; border: 1px solid #E3E7EE; border-radius: 20px;
    box-shadow: 0 7px 18px rgba(17,24,39,.06);
    overflow: hidden; margin-bottom: 14px;
}
.gg-pad { padding: 20px 22px; }
.gg-pill { display:inline-flex; align-items:center; gap:6px; font-size:13px; font-weight:700;
    border-radius:999px; padding:5px 12px; white-space:nowrap; }
.gg-tag { font-size:12px; font-weight:700; color:#7B8597; background:#EEF2F8; border-radius:7px; padding:4px 9px; }
.gg-dot { display:inline-block; width:7px; height:7px; border-radius:50%; }
.gg-bar { position:relative; height:10px; background:#EEF2F7; border-radius:999px; margin-top:16px; }
.gg-bar .zone { position:absolute; top:0; bottom:0; background:rgba(43,174,114,.22); border-radius:999px; }
.gg-bar .mark { position:absolute; top:-5px; width:20px; height:20px; margin-left:-10px; border-radius:50%;
    border:3px solid #fff; box-shadow:0 2px 6px rgba(0,0,0,.28); }
.gg-explain { padding:0 20px 18px; }
.gg-explain .box { background:#F6F9FD; border-radius:13px; padding:16px 18px; border:1px solid #EDF2FA; }
.gg-source { display:flex; align-items:center; gap:6px; margin-top:12px; font-size:12.5px; color:#9099A8; }
.gg-muted { color:#7B8597; }

/* 컨테이너 border 스타일 오버라이드 */
[data-testid="stVerticalBlockBorderWrapper"] > div {
    border-radius: 16px !important; border-color: #E3E7EE !important;
    box-shadow: 0 7px 18px rgba(17,24,39,.05) !important;
}

/* ── 전역 AI 챗봇 패널 ─────────────────────────────── */
.gg-ai-panel {
    position: fixed;
    top: 0;
    bottom: 0;
    left: 21rem;
    width: 400px;
    z-index: 999;
    background: #FFFFFF;
    border-right: 1px solid #D7DEE8;
    box-shadow: 10px 0 24px rgba(17,24,39,.08);
    padding: 22px 22px 18px;
    display: flex;
    flex-direction: column;
    gap: 16px;
}

/* AI 패널이 열리면 본문이 패널 뒤로 깔리지 않도록 실제 main 영역을 오른쪽으로 민다 */
.stApp:has(.gg-ai-panel) section.main,
.stApp:has(.gg-ai-panel) .stMain,
.stApp:has(.gg-ai-panel) [data-testid="stMain"] {
    margin-left: 400px !important;
    width: calc(100% - 400px) !important;
    max-width: calc(100% - 400px) !important;
    transition: margin-left .18s ease, width .18s ease;
}
.stApp:has(.gg-ai-panel) section.main .block-container,
.stApp:has(.gg-ai-panel) .stMain .block-container,
.stApp:has(.gg-ai-panel) [data-testid="stMain"] .block-container {
    padding-left: 2.8rem !important;
    max-width: 1380px !important;
}
.gg-ai-head {
    display:flex; align-items:center; justify-content:space-between; gap:12px;
    background:#F8FAFC; border:1px solid #E3E7EE; border-radius:20px; padding:16px 18px;
}
.gg-ai-title { font-size:16px; font-weight:800; color:#111827; }
.gg-ai-sub, .gg-ai-close { font-size:11px; font-weight:600; color:#667085; margin-top:4px; }
.gg-ai-close { margin-top:0; white-space:nowrap; color:#7A8494; }
.gg-ai-context {
    background:#F8FAFC; border:1px solid #E3E7EE; border-radius:18px; padding:16px 18px;
}
.gg-ai-context-label { font-size:11px; font-weight:800; color:#667085; letter-spacing:.2px; }
.gg-ai-context-body { font-size:13px; font-weight:700; color:#182230; margin-top:7px; line-height:1.5; }
.gg-ai-context-focus { font-size:11px; color:#667085; margin-top:5px; }
.gg-ai-thread {
    flex:1; overflow-y:auto; padding-right:4px; display:flex; flex-direction:column; gap:18px;
}
.gg-ai-row { display:flex; gap:10px; align-items:flex-start; }
.gg-ai-row.user { justify-content:flex-end; }
.gg-ai-avatar {
    width:32px; height:32px; border-radius:12px; background:#EEF3F8; color:#4B617D;
    display:flex; align-items:center; justify-content:center; font-size:11px; font-weight:800; flex:none;
}
.gg-ai-bubble {
    background:#F8FAFC; border:1px solid #E3E7EE; border-radius:18px; padding:14px 16px;
    color:#253044; font-size:13px; line-height:1.65; max-width:300px;
}
.gg-ai-user-bubble {
    background:#234C7D; color:#fff; border-radius:18px; padding:14px 16px;
    font-size:13px; line-height:1.55; max-width:280px;
}
.gg-ai-reco {
    display:grid; grid-template-columns:1fr; gap:8px; margin-top:12px;
}
.gg-ai-reco > div {
    background:#fff; border:1px solid #E3E7EE; border-radius:12px; padding:10px 12px;
    color:#475467; font-size:12px; line-height:1.45;
}
.gg-ai-card-btn {
    width:100%; margin-top:12px; border:1px solid #D7DEE8; background:#fff; color:#173557;
    border-radius:12px; padding:10px 12px; font-size:12px; font-weight:800;
}
.gg-ai-input {
    border:1px solid #D7DEE8; border-radius:18px; padding:10px; display:flex;
    align-items:center; justify-content:space-between; gap:8px; background:#fff;
}
.gg-ai-input span { color:#667085; font-size:12px; padding-left:8px; }
.gg-ai-input button {
    border:0; background:linear-gradient(135deg,#234C7D,#173557); color:#fff;
    border-radius:12px; padding:9px 14px; font-size:12px; font-weight:800;
}

@media (max-width: 900px) {
    .gg-ai-panel {
        left:0; width:auto; right:0; top:0; z-index:1000;
    }
    .gg-auth-grid {
        grid-template-columns: 1fr;
        gap: 20px;
        padding: 28px 18px 40px 18px;
        min-height: auto;
    }
    .gg-auth-brand-panel { display: none !important; }
    .gg-auth-card {
        padding: 28px 22px 24px;
        border-radius: 22px;
    }
    section.main .block-container { padding-left:1rem!important; padding-right:1rem!important; }
}
</style>
"""


def inject_css(st):
    st.markdown(CSS, unsafe_allow_html=True)
