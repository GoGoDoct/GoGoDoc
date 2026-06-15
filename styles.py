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
}
.stApp { background: #F4F6F9; color: #1B2533; }

/* Streamlit 기본 크롬 숨기기 */
#MainMenu, header[data-testid="stHeader"], footer { visibility: hidden; height: 0; }
[data-testid="stToolbar"], [data-testid="stDecoration"] { display: none; }

/* 본문 여백 */
.block-container { padding: 1.6rem 2.4rem 3rem; max-width: 1280px; }

/* ── 사이드바 ─────────────────────────────────────── */
[data-testid="stSidebar"] { background: #FFFFFF; border-right: 1px solid #E4E9F0; }
[data-testid="stSidebar"] .block-container { padding-top: 1.4rem; }

/* ── 버튼 ─────────────────────────────────────────── */
.stButton > button {
    border-radius: 11px; font-weight: 700; font-size: 14px;
    border: 1px solid #DCE3EC; background: #fff; color: #3C4656;
    padding: 0.55rem 1rem; transition: all .15s; box-shadow: none;
}
.stButton > button:hover { border-color: #C2CEDD; background: #F8FAFC; color: #1B2533; }
.stButton > button[kind="primary"] {
    background: #15448A; border: none; color: #fff;
    box-shadow: 0 6px 16px rgba(21,68,138,.25);
}
.stButton > button[kind="primary"]:hover { background: #0F3A78; color: #fff; }

/* 다운로드/링크 버튼 */
.stDownloadButton > button { border-radius: 11px; font-weight: 700; }

/* ── 입력 위젯 ────────────────────────────────────── */
[data-testid="stTextInput"] input, [data-testid="stNumberInput"] input {
    border-radius: 11px !important; border: 1px solid #DCE3EC !important;
    background: #FBFCFE !important; height: 46px; font-size: 14px;
}
[data-testid="stTextInput"] input:focus, [data-testid="stNumberInput"] input:focus {
    border-color: #15448A !important; box-shadow: 0 0 0 3px rgba(21,68,138,.12) !important;
    background: #fff !important;
}
[data-testid="stWidgetLabel"] p { font-size: 13px !important; font-weight: 600; color: #4A5567; }

/* 라디오 → 세그먼트 느낌 */
[data-testid="stRadio"] [role="radiogroup"] { gap: 8px; }

/* 파일 업로더 */
[data-testid="stFileUploader"] section {
    border: 2px dashed #C6D3E4; border-radius: 14px; background: #FAFCFE; padding: 18px;
}
[data-testid="stFileUploader"] section:hover { border-color: #15448A; }

/* 파일 업로더 - 중앙 정렬 및 한글화 (이미지 톤) */
[data-testid="stFileUploaderDropzone"] {
    flex-direction: column; align-items: center; text-align: center; gap: 10px; padding: 30px 18px;
}
[data-testid="stFileUploaderDropzoneInstructions"] {
    display: flex; flex-direction: column; align-items: center;
}
[data-testid="stFileUploaderDropzoneInstructions"] span { font-size: 0; }
[data-testid="stFileUploaderDropzoneInstructions"] span::after {
    content: "결과지 PDF를 끌어다 놓으세요"; font-size: 15px; font-weight: 700; color: #3C4656;
}
[data-testid="stFileUploaderDropzoneInstructions"] small { font-size: 0; }
[data-testid="stFileUploaderDropzoneInstructions"] small::after {
    content: "또는 파일을 선택해 업로드 · 최대 200MB · PDF"; font-size: 12px; color: #9099A8;
}
[data-testid="stFileUploaderDropzone"] button { font-size: 0 !important; }
[data-testid="stFileUploaderDropzone"] button::after {
    content: "파일 선택"; font-size: 14px; font-weight: 700;
}

/* 탭 */
.stTabs [data-baseweb="tab-list"] { gap: 4px; background: #EDF1F6; padding: 4px; border-radius: 10px; }
.stTabs [data-baseweb="tab"] { height: 34px; border-radius: 7px; padding: 0 16px; font-weight: 700; font-size: 13px; color: #7B8597; }
.stTabs [aria-selected="true"] { background: #fff; color: #15448A; box-shadow: 0 1px 3px rgba(27,37,51,.12); }

/* details(쉬운 설명) */
details.gg-details { margin-top: 4px; }
details.gg-details > summary {
    list-style: none; cursor: pointer; padding: 9px 18px; border-top: 1px solid #F2F5F9;
    font-size: 12px; font-weight: 600; color: #15448A;
}
details.gg-details > summary::-webkit-details-marker { display: none; }
details.gg-details[open] > summary { color: #5B6678; }

/* ── 재사용 카드/요소 클래스 ──────────────────────── */
.gg-card { background:#fff; border:1px solid #E4E9F0; border-radius:14px;
    box-shadow:0 2px 10px rgba(27,37,51,.04); overflow:hidden; margin-bottom:12px; }
.gg-pad { padding:16px 18px; }
.gg-pill { display:inline-flex; align-items:center; gap:5px; font-size:11.5px; font-weight:700;
    border-radius:999px; padding:4px 10px; }
.gg-tag { font-size:10.5px; font-weight:700; color:#9099A8; background:#F0F3F8; border-radius:6px; padding:3px 7px; }
.gg-dot { display:inline-block; width:6px; height:6px; border-radius:50%; }
.gg-bar { position:relative; height:8px; background:#EEF2F7; border-radius:999px; margin-top:14px; }
.gg-bar .zone { position:absolute; top:0; bottom:0; background:rgba(43,174,114,.20); border-radius:999px; }
.gg-bar .mark { position:absolute; top:-4px; width:16px; height:16px; margin-left:-8px; border-radius:50%;
    border:3px solid #fff; box-shadow:0 1px 4px rgba(0,0,0,.28); }
.gg-explain { padding:0 18px 16px; }
.gg-explain .box { background:#F8FAFC; border-radius:11px; padding:14px 15px; }
.gg-source { display:flex; align-items:center; gap:6px; margin-top:11px; font-size:11px; color:#9099A8; }
.gg-muted { color:#7B8597; }
</style>
"""


def inject_css(st):
    st.markdown(CSS, unsafe_allow_html=True)
