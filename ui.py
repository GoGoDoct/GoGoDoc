# -*- coding: utf-8 -*-
"""HTML 렌더 헬퍼. st.markdown(..., unsafe_allow_html=True) 로 출력할 문자열을 만든다.

Streamlit 마크다운은 들여쓰기 4칸을 코드블록으로 해석하므로,
여기서 만드는 HTML 문자열은 줄 앞 공백 없이 한 줄로 합쳐서 반환한다.
"""
import os as _os
from sample_data import STATUS, range_text, bar_metrics

def _load_asset_b64(name: str) -> str:
    path = _os.path.join(_os.path.dirname(__file__), "assets", name)
    if name.endswith(".b64"):
        try:
            with open(path, encoding="utf-8") as f:
                return f.read().strip()
        except FileNotFoundError:
            return ""
    try:
        with open(path, "rb") as f:
            import base64 as _base64
            return _base64.b64encode(f.read()).decode("ascii")
    except FileNotFoundError:
        return ""

_ICON_B64 = _load_asset_b64("icon.png")
_WORDMARK_B64 = _load_asset_b64("logo.png")


def brand_lockup_html(icon_width: int = 72, logo_width: int = 150, gap: int = 14) -> str:
    """아이콘과 워드마크를 한 줄로 배치한 브랜드 잠금형 로고."""
    if _ICON_B64 and _WORDMARK_B64:
        return (
            f'<div style="display:flex;align-items:center;gap:{gap}px;max-width:100%">'
            f'<img src="data:image/png;base64,{_ICON_B64}" '
            f'style="width:{icon_width}px;height:auto;display:block;flex:none"/>'
            f'<img src="data:image/png;base64,{_WORDMARK_B64}" '
            f'style="width:{logo_width}px;height:auto;display:block;min-width:0"/>'
            '</div>'
        )

    ecg = (
        '<svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 12h4l2.5 7 4-14 2.5 7H21"/></svg>'
    )
    return (
        '<div style="width:96px;height:96px;border-radius:24px;background:rgba(255,255,255,.12);'
        f'display:flex;align-items:center;justify-content:center">{ecg}</div>'
    )


def _val_label(it):
    return it.get("value_text", it["value"])


def _fmt_num(value) -> str:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    if number.is_integer():
        return str(int(number))
    return f"{number:.1f}"


def _safe_range_text(it: dict) -> str:
    low, high = it.get("low"), it.get("high")
    if low is None and high is None:
        return "기준 정보 없음"
    if high is None:
        return f"{_fmt_num(low)} 이상"
    if low in (None, 0):
        return f"{_fmt_num(high)} 이하"
    return f"{_fmt_num(low)}~{_fmt_num(high)}"


def bar_html(it) -> str:
    marker, n_left, n_width = bar_metrics(it["value"], it["low"], it["high"])
    bar_color = STATUS[it["status"]]["bar"]
    return (
        f'<div class="gg-bar">'
        f'<div class="zone" style="left:{n_left:.1f}%;width:{n_width:.1f}%"></div>'
        f'<div class="mark" style="left:{marker:.1f}%;background:{bar_color}"></div>'
        f'</div>'
    )


def result_card_html(it) -> str:
    """AI 해석 카드 1개 (값 + 정상범위 막대 + 펼쳐보는 쉬운 설명)."""
    s = STATUS[it["status"]]
    border = "#E2E8F2" if it["status"] == "정상" else s["border"]
    accent = s["color"]
    return (
        f'<div class="gg-card" style="border-color:{border};border-left:4px solid {accent}">'
        f'<div class="gg-pad">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:12px">'
        f'<div style="display:flex;align-items:center;gap:10px;min-width:0">'
        f'<span class="gg-tag">{it["cat"]}</span>'
        f'<span style="font-size:16px;font-weight:700;color:#1B2533">{it["name"]}</span>'
        f'</div>'
        f'<span class="gg-pill" style="color:{s["color"]};background:{s["bg"]}">'
        f'<span class="gg-dot" style="background:{s["color"]}"></span>{it["status"]}</span>'
        f'</div>'
        f'<div style="display:flex;align-items:baseline;gap:10px;margin-top:14px">'
        f'<span style="font-size:30px;font-weight:800;color:{s["color"]};line-height:1">{_val_label(it)}</span>'
        f'<span style="font-size:14px;color:#9099A8;font-weight:500">{it["unit"]}</span>'
        f'<span style="font-size:13px;color:#A4ACBA;margin-left:auto">참조 {range_text(it)}</span>'
        f'</div>'
        f'{bar_html(it) if it.get("low") is not None or it.get("high") is not None else ""}'
        f'</div>'
        f'<details class="gg-details"><summary>쉬운 설명 보기</summary>'
        f'<div class="gg-explain"><div class="box">'
        f'<div style="font-size:14.5px;line-height:1.8;color:#3C4656">{it["explain"]}</div>'
        f'<div class="gg-source">🔗 근거: {it["source"]}</div>'
        f'</div></div></details>'
        f'</div>'
    )


def report_table_html(items, gender_short, age) -> str:
    """좌측 '원본 검진 결과지' 통보서 느낌의 표."""
    rows = ""
    for it in items:
        s = STATUS[it["status"]]
        row_bg = "transparent" if it["status"] == "정상" else s["bg"]
        val_color = "#2B3545" if it["status"] == "정상" else s["color"]
        rows += (
            f'<div style="display:grid;grid-template-columns:1.6fr 1fr 1.2fr;align-items:center;'
            f'padding:11px 4px;border-bottom:1px solid #F2F5F9;background:{row_bg}">'
            f'<span style="font-size:12.5px;font-weight:600;color:#2B3545">{it["name"]}</span>'
            f'<span style="text-align:right;font-size:12.5px;font-weight:700;color:{val_color}">'
            f'{_val_label(it)} <span style="font-size:10.5px;font-weight:500;color:#9099A8">{it["unit"]}</span> '
            f'<span class="gg-dot" style="background:{s["bar"]};margin-left:3px;vertical-align:middle"></span></span>'
            f'<span style="text-align:right;font-size:11.5px;color:#8590A1">{range_text(it)}</span>'
            f'</div>'
        )
    return (
        f'<div class="gg-card" style="padding:22px 24px">'
        f'<div style="text-align:center;border-bottom:2px solid #1B2533;padding-bottom:12px">'
        f'<div style="font-size:15px;font-weight:800;letter-spacing:2px">종 합 검 진 결 과 통 보 서</div>'
        f'<div style="font-size:11px;color:#8590A1;margin-top:5px">한빛종합건강검진센터</div></div>'
        f'<div style="display:flex;justify-content:space-between;font-size:11.5px;color:#5B6678;'
        f'margin-top:12px;padding-bottom:12px;border-bottom:1px solid #EDF1F6">'
        f'<span>수검자: 홍길동 ({gender_short}, 만 {age}세)</span><span>검진일: 2026-06-10</span></div>'
        f'<div style="display:grid;grid-template-columns:1.6fr 1fr 1.2fr;margin-top:14px;font-size:11px;'
        f'font-weight:700;color:#8590A1;padding:0 4px 8px;border-bottom:1px solid #E4E9F0">'
        f'<span>검사 항목</span><span style="text-align:right">결과</span><span style="text-align:right">참조 범위</span></div>'
        f'{rows}'
        f'<div style="font-size:10px;color:#A4ACBA;margin-top:14px;line-height:1.6">'
        f'※ 본 통보서는 데모용 샘플 데이터입니다. ● 정상 · ● 주의 · ● 이상</div>'
        f'</div>'
    )


def report_table_top_html(gender_short: str, age: int,
                          user_name: str = "수검자", date_str: str = "") -> str:
    """통보서 제목·환자정보·컬럼 레이블 블록 (카드 래퍼 없음)."""
    date_display = f"검진일: {date_str}" if date_str else "검진일: -"
    return (
        f'<div style="text-align:center;border-bottom:3px solid #1B2533;padding-bottom:14px">'
        f'<div style="font-size:17px;font-weight:850;letter-spacing:3px;color:#1B2533;line-height:1.25">종 합 검 진 결 과 통 보 서</div>'
        f'<div style="font-size:13px;color:#8590A1;margin-top:6px;font-weight:600;line-height:1.35">한빛종합건강검진센터</div></div>'
        f'<div style="display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:13px;color:#5B6678;'
        f'margin-top:14px;padding-bottom:14px;border-bottom:1px solid #EDF1F6;font-weight:650;line-height:1.45">'
        f'<span>수검자: {user_name} ({gender_short}, 만 {age}세)</span><span>{date_display}</span></div>'
        f'<div style="display:grid;grid-template-columns:minmax(180px,1.45fr) minmax(160px,1fr) minmax(160px,1.1fr);'
        f'gap:8px;margin-top:14px;font-size:12.5px;line-height:1.35;'
        f'font-weight:800;color:#8590A1;padding:0 6px 10px;border-bottom:1px solid #E4E9F0;letter-spacing:-.2px">'
        f'<span>검사 항목</span><span style="text-align:right">결과</span>'
        f'<span style="text-align:right">참조 범위</span></div>'
    )


def report_row_html(it: dict, is_selected: bool = False) -> str:
    """단일 검사 항목 행 HTML (선택 여부 강조 포함)."""
    s = STATUS[it["status"]]
    if is_selected:
        row_bg = "#E8F0FB"
        border_left = "4px solid #15448A"
        pl = "10px"
        name_color = "#0F3A78"
    elif it["status"] != "정상":
        row_bg = s["bg"]
        border_left = "none"
        pl = "6px"
        name_color = "#2B3545"
    else:
        row_bg = "transparent"
        border_left = "none"
        pl = "6px"
        name_color = "#2B3545"
    val_color = "#2B3545" if it["status"] == "정상" else s["color"]
    return (
        f'<div style="display:grid;grid-template-columns:1.6fr 1fr 1.2fr;align-items:center;'
        f'padding:13px 6px 13px {pl};border-bottom:1px solid #F0F4FA;background:{row_bg};'
        f'border-left:{border_left};transition:background .15s">'
        f'<span style="font-size:14px;font-weight:600;color:{name_color}">{it["name"]}</span>'
        f'<span style="text-align:right;font-size:14px;font-weight:800;color:{val_color}">'
        f'{_val_label(it)} <span style="font-size:12px;font-weight:500;color:#9099A8">{it["unit"]}</span>'
        f'<span class="gg-dot" style="background:{s["bar"]};margin-left:4px;vertical-align:middle"></span></span>'
        f'<span style="text-align:right;font-size:13px;color:#8590A1;font-weight:500">{range_text(it)}</span>'
        f'</div>'
    )


def report_value_cell_html(it: dict) -> str:
    """검진 결과 행의 결과값 셀."""
    s = STATUS[it["status"]]
    val_color = "#2B3545" if it["status"] == "정상" else s["color"]
    return (
        f'<div style="display:flex;align-items:center;justify-content:center;gap:8px;text-align:center;'
        f'padding:0 8px;border-bottom:1px solid #F0F4FA;height:56px;min-height:56px;white-space:nowrap;overflow:hidden">'
        f'<span style="display:inline-flex;align-items:center;gap:5px;border:1px solid {s["border"]};'
        f'background:{s["bg"]};color:{s["color"]};border-radius:999px;padding:4px 8px;'
        f'font-size:11.5px;font-weight:850;letter-spacing:-.1px;line-height:1.1;flex:none">'
        f'<span style="width:6px;height:6px;border-radius:50%;background:{s["color"]};display:inline-block;flex:none"></span>{it["status"]}</span>'
        f'<span style="font-size:14px;font-weight:900;color:{val_color};line-height:1.2;overflow:hidden;text-overflow:ellipsis;min-width:0">'
        f'{_val_label(it)} <span style="font-size:12px;font-weight:650;color:#9099A8">{it["unit"]}</span></span>'
        f'</div>'
    )


def report_range_cell_html(it: dict) -> str:
    """검진 결과 행의 참조 범위 셀."""
    return (
        '<div style="display:flex;align-items:center;justify-content:center;text-align:center;'
        'font-size:13px;color:#8590A1;font-weight:650;line-height:1.35;'
        'padding:0 8px;border-bottom:1px solid #F0F4FA;height:56px;min-height:56px;word-break:keep-all;'
        'white-space:nowrap;overflow:hidden;text-overflow:ellipsis">'
        f'{_safe_range_text(it)}</div>'
    )


def report_table_note_html() -> str:
    """하단 면책 주석 및 사용 안내."""
    return (
        '<div style="font-size:12px;color:#A4ACBA;margin-top:12px;line-height:1.75;padding-bottom:4px;word-break:keep-all">'
        '※ 데모용 샘플 데이터입니다. ● 정상 · ● 주의 · ● 이상 · '
        '<span style="color:#15448A;font-weight:700">항목명을 클릭하면 쉬운 정의를 볼 수 있어요</span></div>'
    )


def _definition_for_item(name: str, category: str = "") -> str:
    """검진 항목을 일반 사용자가 이해하기 쉬운 말로 설명."""
    n = (name or "").lower()
    c = category or ""
    definitions = [
        (("ldl", "저밀도"), "LDL은 혈관 벽에 콜레스테롤을 쌓이게 하기 쉬운 운반체입니다. 흔히 나쁜 콜레스테롤이라고 부르며, 높을수록 혈관 건강을 함께 확인하는 것이 좋습니다."),
        (("hdl", "고밀도"), "HDL은 혈관에 남은 콜레스테롤을 간으로 가져가 정리하는 데 도움을 주는 운반체입니다. 흔히 좋은 콜레스테롤이라고 부릅니다."),
        (("총콜레스테롤", "콜레스테롤"), "콜레스테롤은 세포막과 호르몬을 만드는 데 필요한 지방 성분입니다. 다만 혈액 속에 너무 많으면 혈관 벽에 쌓여 혈액 흐름에 부담을 줄 수 있습니다."),
        (("중성지방", "triglyceride", "tg"), "중성지방은 음식으로 섭취한 에너지 중 남은 부분이 지방 형태로 저장된 것입니다. 높으면 혈당, 체중, 혈관 건강을 함께 살펴보는 것이 좋습니다."),
        (("공복혈당", "혈당", "glucose"), "혈당은 혈액 속 포도당의 양입니다. 포도당은 몸의 주요 에너지원이며, 공복 상태에서 높게 나오면 당 조절 상태를 확인해야 합니다."),
        (("당화혈색소", "hba1c"), "당화혈색소는 최근 2~3개월 동안의 평균 혈당 흐름을 보여주는 지표입니다. 하루의 일시적인 혈당보다 장기적인 당 조절 상태를 보는 데 도움이 됩니다."),
        (("ast", "got"), "AST는 간, 심장, 근육 등에 있는 효소입니다. 수치가 높으면 간이나 근육이 자극을 받았는지 함께 확인합니다."),
        (("alt", "gpt"), "ALT는 주로 간세포 안에 있는 효소입니다. 간세포가 손상되거나 부담을 받으면 혈액에서 높게 보일 수 있습니다."),
        (("감마", "γ", "ggt", "gtp"), "감마지티피는 간과 담도 상태를 볼 때 참고하는 효소입니다. 음주, 지방간, 담도 문제와 관련되어 높아질 수 있습니다."),
        (("크레아티닌", "creatinine"), "크레아티닌은 근육에서 만들어져 콩팥을 통해 배출되는 노폐물입니다. 콩팥이 노폐물을 잘 걸러내는지 확인할 때 사용합니다."),
        (("egfr", "사구체"), "eGFR은 콩팥이 혈액을 얼마나 잘 걸러내는지 추정한 값입니다. 낮을수록 콩팥 기능을 더 주의 깊게 살펴봐야 합니다."),
        (("요소질소", "bun"), "요소질소는 단백질이 분해된 뒤 생기는 노폐물입니다. 콩팥 기능, 수분 상태, 단백질 섭취 상태를 함께 볼 때 참고합니다."),
        (("혈압", "수축기", "이완기"), "혈압은 심장이 피를 보낼 때 혈관에 가해지는 압력입니다. 지속적으로 높으면 심장과 혈관에 부담이 커질 수 있습니다."),
        (("헤모글로빈", "혈색소", "hemoglobin", " hb"), "헤모글로빈은 적혈구 안에서 산소를 운반하는 단백질입니다. 낮으면 빈혈 가능성을, 높으면 혈액 농축 상태 등을 함께 봅니다."),
        (("백혈구", "wbc"), "백혈구는 세균이나 바이러스 같은 외부 자극에 대응하는 면역 세포입니다. 염증이나 감염 여부를 확인할 때 참고합니다."),
        (("혈소판", "platelet", "plt"), "혈소판은 피가 났을 때 지혈을 돕는 작은 혈액 성분입니다. 너무 낮거나 높으면 출혈 또는 혈전 위험과 관련해 확인이 필요합니다."),
        (("요산", "uric"), "요산은 음식과 몸속 세포에서 나온 퓨린이라는 물질이 분해되며 생기는 노폐물입니다. 높으면 통풍이나 신장 부담과 관련될 수 있습니다."),
        (("tsh", "갑상선"), "TSH는 갑상선 호르몬 분비를 조절하라고 신호를 보내는 호르몬입니다. 갑상선 기능이 적절한지 확인하는 데 사용합니다."),
        (("bmi", "체질량", "비만"), "BMI는 키와 몸무게를 이용해 체중 상태를 대략적으로 보는 지표입니다. 근육량은 반영하지 못하므로 다른 건강 지표와 함께 보는 것이 좋습니다."),
        (("시력",), "시력은 눈이 사물을 얼마나 선명하게 구분하는지 보여주는 지표입니다. 변화가 크거나 불편감이 있으면 안과 확인이 도움이 됩니다."),
        (("청력",), "청력은 소리를 듣고 구분하는 능력을 확인하는 항목입니다. 한쪽만 떨어지거나 일상 대화가 불편하면 추가 검사를 고려합니다."),
    ]
    for keys, text in definitions:
        if any(key in n for key in keys):
            return text

    category_fallbacks = {
        "지질": "지질 항목은 혈액 속 지방 성분의 상태를 보는 검사입니다. 혈관 건강과 심혈관 질환 위험을 판단할 때 참고합니다.",
        "혈당": "혈당 항목은 몸이 포도당을 얼마나 안정적으로 조절하는지 확인하는 검사입니다. 당뇨병 위험을 살펴볼 때 중요합니다.",
        "간기능": "간기능 항목은 간이 영양소 처리와 해독을 하는 과정에서 관련 효소가 혈액에 얼마나 보이는지 확인하는 검사입니다.",
        "신장": "신장 항목은 콩팥이 노폐물을 걸러내고 몸의 수분 균형을 조절하는 기능을 확인하는 검사입니다.",
        "혈액": "혈액 항목은 산소 운반, 면역 반응, 지혈 기능처럼 혈액의 기본 상태를 확인하는 검사입니다.",
        "혈압": "혈압 항목은 혈관에 가해지는 압력을 확인해 심장과 혈관에 부담이 있는지 살펴보는 지표입니다.",
    }
    return category_fallbacks.get(c, "이 항목은 검진에서 몸 상태를 간접적으로 확인하기 위해 측정하는 지표입니다. 수치 하나만으로 판단하기보다 다른 검사 결과와 증상을 함께 보는 것이 좋습니다.")


def _has_final_consonant(text: str) -> bool:
    """마지막 한글 음절의 받침 여부 확인."""
    for char in reversed((text or "").strip()):
        code = ord(char)
        if 0xAC00 <= code <= 0xD7A3:
            return (code - 0xAC00) % 28 != 0
        if char.isalnum():
            return False
    return False


def definition_question(name: str) -> str:
    """항목명에 맞는 '이란/란' 질문 문구."""
    particle = "이란?" if _has_final_consonant(name) else "란?"
    return f"{name}{particle}"


def result_comparison_html(it: dict) -> str:
    """표준 기준과 내 검사 결과 비교 시각화."""
    value = it.get("value")
    try:
        numeric_value = float(value)
    except (TypeError, ValueError):
        return ""

    low, high = it.get("low"), it.get("high")
    if low is None and high is None:
        return (
            '<div style="margin-top:14px;border:1px solid #E5EAF2;border-radius:16px;background:#FFFFFF;padding:14px 16px">'
            '<div style="font-size:14px;font-weight:850;color:#111827;margin-bottom:8px;line-height:1.3">표준 기준과 내 결과 비교</div>'
            '<div style="font-size:14px;line-height:1.7;color:#64748B;word-break:keep-all">이 항목은 표준 기준값이 제공되지 않아 수치 위치 비교를 표시하지 않습니다.</div>'
            '</div>'
        )

    marker, normal_left, normal_width = bar_metrics(numeric_value, low, high)
    s = STATUS[it["status"]]
    unit = it.get("unit", "")
    standard_label = _safe_range_text(it)
    value_label = f'{_val_label(it)} {unit}'.strip()

    if high is not None and numeric_value > float(high):
        diff = numeric_value - float(high)
        compare_text = f'기준 상한보다 {_fmt_num(diff)} {unit} 높습니다.'.strip()
    elif low is not None and numeric_value < float(low):
        diff = float(low) - numeric_value
        compare_text = f'기준 하한보다 {_fmt_num(diff)} {unit} 낮습니다.'.strip()
    else:
        compare_text = "표준 기준 범위 안에 위치합니다."

    left_label = _fmt_num(low) if low is not None else "0"
    right_label = _fmt_num(high) if high is not None else "상한 참고"
    normal_label = "표준 기준 구간"
    if high is None and low is not None:
        normal_label = f'{_fmt_num(low)} 이상 기준'
    elif low in (None, 0) and high is not None:
        normal_label = f'{_fmt_num(high)} 이하 기준'

    return (
        '<div style="margin-top:15px;border:1px solid #DDE6F2;border-radius:18px;background:#FFFFFF;'
        'box-shadow:0 8px 22px rgba(15,23,42,.05);padding:15px 16px">'
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin-bottom:13px;flex-wrap:wrap">'
        '<div style="font-size:15px;font-weight:850;color:#111827;line-height:1.3">표준 기준과 내 결과 비교</div>'
        f'<span style="display:inline-flex;align-items:center;border:1px solid {s["border"]};background:{s["bg"]};'
        f'color:{s["color"]};border-radius:999px;padding:5px 10px;font-size:12px;font-weight:850;line-height:1.1">{it["status"]}</span>'
        '</div>'
        '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:9px;margin-bottom:15px">'
        '<div style="background:#F8FAFC;border:1px solid #E5EAF2;border-radius:14px;padding:11px 12px">'
        '<div style="font-size:11.5px;color:#64748B;font-weight:800;margin-bottom:6px;line-height:1.25">표준 기준</div>'
        f'<div style="font-size:15px;color:#1F2937;font-weight:850;line-height:1.25;word-break:keep-all">{standard_label}</div></div>'
        '<div style="background:#F8FAFC;border:1px solid #E5EAF2;border-radius:14px;padding:11px 12px">'
        '<div style="font-size:11.5px;color:#64748B;font-weight:800;margin-bottom:6px;line-height:1.25">내 검사 결과</div>'
        f'<div style="font-size:15px;color:{s["color"]};font-weight:900;line-height:1.25;word-break:keep-all">{value_label}</div></div>'
        '<div style="background:#F8FAFC;border:1px solid #E5EAF2;border-radius:14px;padding:11px 12px">'
        '<div style="font-size:11.5px;color:#64748B;font-weight:800;margin-bottom:6px;line-height:1.25">비교 결과</div>'
        f'<div style="font-size:13.5px;color:#334155;font-weight:750;line-height:1.5;word-break:keep-all">{compare_text}</div></div>'
        '</div>'
        '<div style="position:relative;height:38px;margin:4px 2px 8px">'
        '<div style="position:absolute;left:0;right:0;top:17px;height:8px;background:#E9EEF5;border-radius:999px;overflow:hidden">'
        f'<div style="position:absolute;left:{normal_left:.1f}%;width:{normal_width:.1f}%;height:8px;'
        'background:#DCEBDD;border-left:1px solid #7EB28D;border-right:1px solid #7EB28D"></div>'
        '</div>'
        f'<div style="position:absolute;left:{marker:.1f}%;top:4px;transform:translateX(-50%);'
        f'display:flex;flex-direction:column;align-items:center;gap:3px">'
        f'<div style="background:{s["color"]};color:#fff;border-radius:999px;padding:3px 8px;'
        f'font-size:11px;font-weight:850;white-space:nowrap;line-height:1.15">내 결과</div>'
        f'<div style="width:3px;height:17px;background:{s["color"]};border-radius:999px"></div>'
        '</div>'
        '</div>'
        '<div style="display:flex;justify-content:space-between;align-items:center;gap:8px;font-size:11.5px;color:#7A8494;font-weight:750;line-height:1.3;word-break:keep-all">'
        f'<span>{left_label}</span><span style="color:#3F7B54">{normal_label}</span><span>{right_label}</span>'
        '</div>'
        '</div>'
    )


def item_definition_card_html(it: dict) -> str:
    """선택한 검진 항목의 쉬운 정의 카드."""
    s = STATUS[it["status"]]
    accent = s["color"]
    definition = _definition_for_item(it.get("name", ""), it.get("cat", ""))
    return (
        f'<div class="gg-card" style="border-color:#E2E8F2;border-left:5px solid {accent}">'
        f'<div class="gg-pad" style="padding:18px 20px">'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:12px;margin-bottom:16px;flex-wrap:wrap">'
        f'<div>'
        f'<div style="font-size:12px;font-weight:800;color:#64748B;letter-spacing:.4px;text-transform:uppercase;margin-bottom:7px;line-height:1.25">항목 정의</div>'
        f'<div style="font-size:23px;font-weight:850;color:#111827;letter-spacing:-.5px;line-height:1.25;word-break:keep-all">{definition_question(it["name"])}</div>'
        f'</div>'
        f'<span class="gg-pill" style="color:{s["color"]};background:{s["bg"]};border:1px solid {s["border"]};'
        f'font-size:12px;padding:5px 10px;line-height:1.15">'
        f'<span class="gg-dot" style="background:{s["color"]}"></span>{it["status"]}</span>'
        f'</div>'
        f'<div style="font-size:16px;line-height:1.85;color:#2F3A4A;background:#F8FAFC;'
        f'border:1px solid #E5EAF2;border-radius:16px;padding:15px 16px;word-break:keep-all">{definition}</div>'
        f'<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px;margin-top:13px">'
        f'<div style="border:1px solid #E5EAF2;border-radius:14px;padding:13px 14px;background:#FFFFFF">'
        f'<div style="font-size:12px;color:#64748B;font-weight:750;margin-bottom:7px;line-height:1.25">현재 결과</div>'
        f'<div style="font-size:25px;font-weight:850;color:{accent};line-height:1.1">{_val_label(it)}'
        f'<span style="font-size:13px;color:#94A3B8;font-weight:650;margin-left:5px">{it["unit"]}</span></div>'
        f'</div>'
        f'<div style="border:1px solid #E5EAF2;border-radius:14px;padding:13px 14px;background:#FFFFFF">'
        f'<div style="font-size:12px;color:#64748B;font-weight:750;margin-bottom:7px;line-height:1.25">참고 범위</div>'
        f'<div style="font-size:15px;font-weight:750;color:#334155;line-height:1.35;word-break:keep-all">{_safe_range_text(it)}</div>'
        f'</div>'
        f'</div>'
        f'{result_comparison_html(it)}'
        f'<div style="font-size:12px;line-height:1.75;color:#7A8494;margin-top:13px;word-break:keep-all">'
        f'이 설명은 항목의 의미를 이해하기 위한 기본 안내입니다. 결과 해석과 관리 방향은 오른쪽 종합 가이드라인과 의료진 상담을 함께 참고하세요.</div>'
        f'</div>'
        f'</div>'
    )


def result_card_detail_html(it: dict, guide: dict | None = None) -> str:
    """선택된 항목 상세 AI 해석 카드 (설명 펼침 + 생활 가이드)."""
    s = STATUS[it["status"]]
    accent = s["color"]
    guide_html = ""
    if guide:
        guide_html = (
            f'<div style="margin-top:20px;padding-top:18px;border-top:1px dashed #E2E8F2">'
            f'<div style="font-size:14px;font-weight:800;color:#15448A;margin-bottom:12px">🌿 생활 가이드</div>'
            f'<div style="background:#F6F9FD;border:1px solid #DCE8F5;border-radius:14px;padding:18px 20px">'
            f'<div style="display:flex;align-items:center;gap:9px;margin-bottom:12px">'
            f'<span class="gg-tag">{guide["category"]}</span>'
            f'<span style="font-size:13px;color:#15448A;font-weight:700;background:#DCE8F5;'
            f'border-radius:8px;padding:4px 11px">권장 진료과 · {guide["department"]}</span></div>'
            f'<div style="font-size:15px;line-height:1.8;color:#3C4656">💡 {guide["lifestyle"]}</div>'
            f'<div style="font-size:14px;line-height:1.7;color:#5B6678;margin-top:10px">📅 추적 · {guide["tracking"]}</div>'
            f'<div class="gg-source" style="margin-top:11px;font-size:13px">🔗 근거: {guide["source"]}</div>'
            f'</div></div>'
        )
    return (
        f'<div class="gg-card" style="border-color:{accent};border-width:2px;border-left:6px solid {accent}">'
        # 컬러 헤더 스트립
        f'<div style="background:linear-gradient(135deg,{s["bg"]},{s["bg"]}88);padding:14px 22px 12px;'
        f'border-bottom:1px solid {s["border"]}">'
        f'<div style="font-size:12.5px;font-weight:700;color:{accent};margin-bottom:8px;'
        f'display:flex;align-items:center;gap:6px">'
        f'<span style="background:{accent};color:#fff;border-radius:5px;padding:2px 8px;font-size:11px">▶ 상세 해석</span>'
        f'</div>'
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:12px">'
        f'<div style="display:flex;align-items:center;gap:10px;min-width:0">'
        f'<span class="gg-tag">{it["cat"]}</span>'
        f'<span style="font-size:19px;font-weight:800;color:#1B2533">{it["name"]}</span>'
        f'</div>'
        f'<span class="gg-pill" style="color:{s["color"]};background:rgba(255,255,255,.8)">'
        f'<span class="gg-dot" style="background:{s["color"]}"></span>{it["status"]}</span>'
        f'</div>'
        f'<div style="display:flex;align-items:baseline;gap:10px;margin-top:16px">'
        f'<span style="font-size:40px;font-weight:800;color:{accent};line-height:1">{_val_label(it)}</span>'
        f'<span style="font-size:16px;color:#9099A8;font-weight:500">{it["unit"]}</span>'
        f'<span style="font-size:13.5px;color:#A4ACBA;margin-left:auto">참조 {range_text(it)}</span>'
        f'</div>'
        f'</div>'
        # 본문
        f'<div class="gg-pad">'
        f'{bar_html(it) if it.get("low") is not None or it.get("high") is not None else ""}'
        f'<div style="margin-top:18px;padding:18px 20px;background:#F6F9FD;border-radius:14px;'
        f'border:1px solid #E2EAF5">'
        f'<div style="font-size:15px;line-height:1.85;color:#3C4656">{it["explain"]}</div>'
        f'<div class="gg-source" style="margin-top:12px;font-size:13px">🔗 근거: {it["source"]}</div>'
        f'</div>'
        f'{guide_html}'
        f'</div>'
        f'</div>'
    )


def dashboard_hero_html(user_name: str, sub: str, days_elapsed: int | None = None) -> str:
    """대시보드 상단 인사말 + 검진 경과일 배지."""
    badge = ""
    if days_elapsed is not None:
        if days_elapsed <= 30:
            dot_color, badge_bg, text_color = "#059669", "#ECFDF5", "#065F46"
        elif days_elapsed <= 60:
            dot_color, badge_bg, text_color = "#D97706", "#FFFBEB", "#92400E"
        else:
            dot_color, badge_bg, text_color = "#DC2626", "#FEF2F2", "#991B1B"
        label = f"검진 후 {days_elapsed}일" if days_elapsed <= 60 else f"검진 후 {days_elapsed}일 · 재검 권장"
        badge = (
            f'<span style="display:inline-flex;align-items:center;gap:6px;'
            f'background:{badge_bg};color:{text_color};border:1px solid {badge_bg};'
            f'font-size:11.5px;font-weight:700;letter-spacing:.1px;border-radius:6px;'
            f'padding:3px 10px;margin-left:14px;vertical-align:middle">'
            f'<span style="width:6px;height:6px;border-radius:50%;background:{dot_color};'
            f'display:inline-block;flex:none"></span>{label}</span>'
        )
    return (
        f'<p style="font-size:11.5px;font-weight:700;color:#64748B;letter-spacing:.6px;'
        f'text-transform:uppercase;margin:0 0 8px">대시보드</p>'
        f'<h1 style="font-size:26px;font-weight:800;color:#0D1117;margin:0;letter-spacing:-.5px;line-height:1.3">'
        f'{user_name}님의 건강 요약{badge}</h1>'
        f'<p style="font-size:13.5px;color:#64748B;margin:8px 0 0;font-weight:500">{sub}</p>'
    )


def dashboard_empty_html() -> str:
    """검진 기록이 없을 때 표시하는 빈 상태 카드."""
    icon = (
        '<svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" '
        'stroke-width="1.4" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
        '<path d="M14 2v6h6"/><line x1="12" y1="18" x2="12" y2="12"/>'
        '<line x1="9" y1="15" x2="15" y2="15"/></svg>'
    )
    items = [
        ("공인 의료 기준 근거로 항목별 자동 분류", "#059669"),
        ("정상·주의·이상 수치를 한눈에 정리", "#0F3460"),
        ("추적 관찰 항목 자동 선정 및 재검 일정 안내", "#0F3460"),
    ]
    checks = "".join(
        f'<div style="display:flex;align-items:flex-start;gap:10px;padding:10px 0;'
        f'border-top:1px solid #F1F5F9">'
        f'<span style="width:18px;height:18px;border-radius:50%;background:{c};'
        f'display:flex;align-items:center;justify-content:center;flex:none;margin-top:1px">'
        f'<svg width="10" height="10" viewBox="0 0 12 12" fill="none"><path d="M2 6l3 3 5-5" '
        f'stroke="#fff" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg></span>'
        f'<span style="font-size:13.5px;color:#475569;line-height:1.5">{t}</span></div>'
        for t, c in items
    )
    return (
        '<div style="background:#fff;border:1px solid #E2E8F0;border-radius:16px;'
        'padding:48px 40px;margin-top:24px;display:flex;gap:56px;align-items:center">'
        '<div style="flex:none;width:72px;height:72px;border-radius:16px;background:#F8FAFC;'
        f'border:1px solid #E2E8F0;display:flex;align-items:center;justify-content:center">'
        f'{icon}</div>'
        '<div style="flex:1">'
        '<div style="font-size:17px;font-weight:800;color:#0D1117;letter-spacing:-.3px">'
        '검진 결과지를 업로드하면 시작됩니다</div>'
        '<div style="font-size:13.5px;color:#64748B;margin-top:6px;line-height:1.65">'
        'PDF 한 장으로 항목별 해석과 생활 가이드를 즉시 확인할 수 있습니다.</div>'
        f'<div style="margin-top:16px">{checks}</div>'
        '</div></div>'
    )


def disclaimer_html() -> str:
    info_icon = (
        '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="flex:none;margin-top:1px">'
        '<circle cx="12" cy="12" r="10"/>'
        '<line x1="12" y1="8" x2="12" y2="8" stroke-width="3"/>'
        '<line x1="12" y1="12" x2="12" y2="16"/></svg>'
    )
    return (
        f'<div style="display:flex;gap:10px;align-items:flex-start;background:#F8FAFC;'
        f'border:1px solid #E2E8F0;border-radius:10px;padding:14px 16px;margin-top:12px">'
        f'{info_icon}'
        f'<div style="font-size:12.5px;line-height:1.65;color:#64748B">'
        f'본 해석은 공인 의료 기준을 근거로 한 <b style="color:#475569">참고용 정보이며 의료 진단이 아닙니다.</b> '
        f'정확한 진단과 치료는 반드시 의료진과 상담하시기 바랍니다.</div></div>'
    )


def emergency_banner_html(it) -> str:
    return (
        '<div style="display:flex;align-items:center;gap:14px;background:#B02A20;color:#fff;'
        'border-radius:14px;padding:15px 18px;margin:14px 0;box-shadow:0 6px 18px rgba(176,42,32,.3)">'
        '<span style="font-size:22px">⚠</span><div>'
        '<div style="font-size:14.5px;font-weight:800">응급 이상치가 감지되었습니다 — 즉시 내원을 권고합니다</div>'
        f'<div style="font-size:12.5px;opacity:.92;margin-top:3px">{it["name"]} {it["value"]} {it["unit"]} '
        '(응급 기준 500 초과). 지체 없이 가까운 응급실 또는 의료기관에 방문하세요.</div></div></div>'
    )


def summary_pills_html(normal, caution, abnormal) -> str:
    total = normal + caution + abnormal

    def pill(n, label, color, tint, caption):
        pct = round(n / total * 100) if total else 0
        return (
            f'<div style="position:relative;min-width:158px;flex:1;background:#FFFFFF;border:1px solid #DDE5F0;'
            f'border-radius:16px;padding:13px 15px 12px;box-shadow:0 10px 26px rgba(15,23,42,.045);overflow:hidden">'
            f'<div style="position:absolute;left:0;top:0;bottom:0;width:5px;background:{color}"></div>'
            f'<div style="display:flex;align-items:center;justify-content:space-between;gap:10px">'
            f'<div style="font-size:13px;font-weight:850;color:#334155;letter-spacing:-.1px;line-height:1.2">{label}</div>'
            f'<span style="width:9px;height:9px;border-radius:50%;background:{color};box-shadow:0 0 0 4px {tint};flex:none"></span>'
            f'</div>'
            f'<div style="display:flex;align-items:flex-end;gap:6px;margin-top:9px">'
            f'<span style="font-size:24px;font-weight:850;color:#111827;letter-spacing:-.5px;line-height:.95">{n}</span>'
            f'<span style="font-size:11px;font-weight:750;color:#64748B;margin-bottom:3px">개</span>'
            f'</div>'
            f'<div style="height:4px;background:#EEF2F7;border-radius:999px;margin-top:10px;overflow:hidden">'
            f'<div style="height:4px;width:{pct}%;background:{color};border-radius:999px"></div>'
            f'</div>'
            f'<div style="font-size:10px;font-weight:650;color:#64748B;line-height:1.35;margin-top:7px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{caption}</div>'
            f'</div>'
        )
    return (
        '<div style="display:flex;gap:14px;justify-content:flex-end;align-items:stretch;flex-wrap:wrap">'
        + pill(normal, "정상", "#2F7D55", "#E6F3EC", "기준 범위 내 항목")
        + pill(caution, "주의", "#A66A16", "#F8ECD7", "추적 확인 필요")
        + pill(abnormal, "이상", "#A9473A", "#F6E6E2", "재확인 권장")
        + '</div>'
    )


def summary_block_html(summary: str) -> str:
    """AI 종합 요약 블록 - 직장인용 결과 요약 (근거 기반 LLM 생성)."""
    return (
        '<div style="background:linear-gradient(135deg,#EDF4FF,#E0EDFF);border:1px solid #C8DEFF;'
        'border-radius:18px;padding:20px 24px;margin:16px 0;border-left:5px solid #15448A">'
        '<div style="display:flex;align-items:center;gap:9px;font-size:15px;font-weight:800;color:#15448A">'
        '<span style="font-size:18px">🩺</span>AI 종합 요약</div>'
        f'<div style="font-size:15.5px;line-height:1.9;color:#2B3545;margin-top:12px">{summary}</div>'
        '</div>'
    )


def overall_guideline_html(summary: str) -> str:
    """PDF 분석 오른쪽 패널에 표시하는 LLM 종합 가이드라인."""
    body = summary or (
        "분석된 항목을 바탕으로 종합 가이드라인을 생성하지 못했습니다. "
        "수치별 의미는 왼쪽 표의 항목명을 눌러 확인해 주세요."
    )
    return (
        '<div class="gg-card" style="border:1px solid #D8E1EE;box-shadow:0 14px 32px rgba(15,23,42,.07)">'
        '<div class="gg-pad" style="padding:18px 20px">'
        '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:14px;flex-wrap:wrap">'
        '<div>'
        '<div style="font-size:12px;font-weight:800;color:#64748B;letter-spacing:.4px;text-transform:uppercase;margin-bottom:7px;line-height:1.25">'
        'Comprehensive Guide</div>'
        '<div style="font-size:22px;font-weight:850;color:#111827;letter-spacing:-.45px;line-height:1.25">AI 종합 가이드라인</div>'
        '</div>'
        '<span style="display:inline-flex;align-items:center;border:1px solid #C7D6EA;background:#F3F7FC;'
        'border-radius:999px;padding:5px 10px;font-size:12px;font-weight:750;color:#27446B;white-space:nowrap;line-height:1.15">전체 항목 기준</span>'
        '</div>'
        f'<div style="font-size:15.5px;line-height:1.85;color:#2F3A4A;background:#F8FAFC;'
        f'border:1px solid #E5EAF2;border-radius:16px;padding:15px 16px;word-break:keep-all">{body}</div>'
        '<div style="font-size:12px;line-height:1.75;color:#7A8494;margin-top:13px;word-break:keep-all">'
        '이 가이드라인은 업로드된 검진 항목 전체를 함께 고려한 참고용 안내입니다. 진단이나 처방을 대신하지 않으며, 증상이 있거나 수치가 크게 벗어난 경우 의료진과 상담하세요.'
        '</div>'
        '</div>'
        '</div>'
    )


def lifestyle_guide_html(guides) -> str:
    """카테고리별 생활 가이드 카드 - 관리법·추적·권장 진료과·출처."""
    if not guides:
        return ""
    cards = ""
    for g in guides:
        cards += (
            '<div style="background:#fff;border:1px solid #E2E8F2;border-radius:16px;padding:18px 20px;margin-top:12px;'
            'box-shadow:0 2px 10px rgba(27,37,51,.05)">'
            '<div style="display:flex;align-items:center;gap:9px">'
            f'<span class="gg-tag">{g["category"]}</span>'
            '<span style="font-size:13px;color:#15448A;font-weight:700;background:#E0EDFF;'
            f'border-radius:8px;padding:4px 11px">권장 진료과 · {g["department"]}</span></div>'
            f'<div style="font-size:15px;line-height:1.8;color:#2B3545;margin-top:13px">💡 {g["lifestyle"]}</div>'
            f'<div style="font-size:14px;line-height:1.7;color:#5B6678;margin-top:9px">📅 추적 · {g["tracking"]}</div>'
            f'<div class="gg-source" style="margin-top:11px;font-size:13px">🔗 근거: {g["source"]}</div>'
            '</div>'
        )
    return (
        '<div style="margin-top:18px">'
        '<div style="font-size:14px;font-weight:800;color:#15448A;margin-bottom:4px">🌿 생활 가이드</div>'
        f'{cards}</div>'
    )


# ── 대시보드 ──────────────────────────────────────────
def kpi_cards_html(normal: int, caution: int, abnormal: int, emergency: int = 0) -> str:
    total = normal + caution + abnormal
    manage = caution + abnormal + emergency
    score_pct = round(normal / total * 100) if total else 0

    if score_pct >= 80:
        score_label, score_color, score_bg = "양호", "#059669", "#ECFDF5"
    elif score_pct >= 60:
        score_label, score_color, score_bg = "주의 필요", "#D97706", "#FFFBEB"
    else:
        score_label, score_color, score_bg = "관리 필요", "#DC2626", "#FEF2F2"

    def metric_card(label, val, desc, line_color, bar_color):
        pct = round(val / total * 100) if total else 0
        return (
            f'<div style="background:#fff;border:1px solid #E2E8F0;border-radius:14px;'
            f'padding:20px 20px 16px;border-left:3px solid {line_color}">'
            f'<div style="font-size:11px;font-weight:700;color:#94A3B8;letter-spacing:.5px;'
            f'text-transform:uppercase">{label}</div>'
            f'<div style="font-size:34px;font-weight:800;color:#0D1117;line-height:1;margin-top:8px">{val}</div>'
            f'<div style="font-size:12px;color:#94A3B8;margin-top:5px;font-weight:500">{desc}</div>'
            f'<div style="height:3px;background:#F1F5F9;border-radius:99px;margin-top:14px">'
            f'<div style="width:{pct}%;height:100%;background:{bar_color};border-radius:99px;'
            f'transition:width .3s ease"></div></div></div>'
        )

    big = (
        f'<div style="background:#fff;border:1px solid #E2E8F0;border-radius:14px;'
        f'padding:24px 24px 20px;box-shadow:0 1px 3px rgba(0,0,0,.05)">'
        f'<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">'
        f'<div style="font-size:11px;font-weight:700;color:#94A3B8;letter-spacing:.5px;'
        f'text-transform:uppercase;padding-top:2px">관리 필요 항목</div>'
        f'<div style="font-size:11.5px;font-weight:700;color:{score_color};background:{score_bg};'
        f'border-radius:6px;padding:3px 10px;white-space:nowrap">{score_label} · 정상 {score_pct}%</div>'
        f'</div>'
        f'<div style="display:flex;align-items:baseline;gap:6px;margin-top:10px">'
        f'<span style="font-size:52px;font-weight:800;color:#0D1117;line-height:1;letter-spacing:-2px">{manage}</span>'
        f'<span style="font-size:16px;color:#94A3B8;font-weight:500">/ {total}개</span>'
        f'</div>'
        f'<div style="height:3px;background:#F1F5F9;border-radius:99px;margin-top:18px">'
        f'<div style="width:{round(manage/total*100) if total else 0}%;height:100%;'
        f'background:{"#DC2626" if score_pct < 60 else "#D97706" if score_pct < 80 else "#059669"};'
        f'border-radius:99px"></div></div>'
        f'<div style="font-size:12.5px;color:#64748B;margin-top:10px;line-height:1.6;font-weight:500">'
        f'{"전체 항목이 정상 범위입니다." if manage == 0 else f"주의 {caution}개 · 이상 {abnormal}개" + (" · 응급 " + str(emergency) + "개" if emergency else "")}'
        f'</div></div>'
    )

    return (
        '<div style="display:grid;grid-template-columns:1.5fr 1fr 1fr 1fr;gap:12px;margin-top:24px">'
        + big
        + metric_card("정상", normal, f"전체 {total}개 중", "#CBD5E1", "#94A3B8")
        + metric_card("주의", caution, "추적 관찰 권장", "#FCD34D", "#D97706")
        + metric_card("이상", abnormal, "재검 필요", "#FCA5A5", "#DC2626")
        + '</div>'
    )


def records_html(records) -> str:
    doc_icon = _line_icon('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
                          '<path d="M14 2v6h6"/>', 18)
    chevron = _line_icon('<path d="M9 18l6-6-6-6"/>', 18)
    rows = ""
    for r in records:
        if r["abnormal"]:
            ic_col, ic_bg = "#C0392B", "#FBEAE8"
        elif r["caution"]:
            ic_col, ic_bg = "#B26A00", "#FBF1E0"
        else:
            ic_col, ic_bg = "#1F8A5B", "#E7F5EE"
        rows += (
            '<div style="display:flex;align-items:center;gap:14px;padding:14px 0;border-top:1px solid #F2F5F9">'
            f'<div style="width:44px;height:44px;flex:none;border-radius:12px;background:{ic_bg};color:{ic_col};'
            f'display:flex;align-items:center;justify-content:center">{doc_icon}</div>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="font-size:14px;font-weight:700;color:#1B2533">{r["title"]}</div>'
            f'<div style="font-size:12px;color:#8590A1;margin-top:3px">{r["date"]}</div></div>'
            '<div style="display:flex;gap:6px;flex:none;align-items:center">'
            f'<span style="font-size:11.5px;font-weight:700;color:#1F8A5B;background:#E7F5EE;'
            f'border-radius:7px;padding:3px 9px">정상 {r["normal"]}</span>'
            f'<span style="font-size:11.5px;font-weight:700;color:#B26A00;background:#FBF1E0;'
            f'border-radius:7px;padding:3px 9px">주의 {r["caution"]}</span>'
            f'<span style="font-size:11.5px;font-weight:700;color:#C0392B;background:#FBEAE8;'
            f'border-radius:7px;padding:3px 9px">이상 {r["abnormal"]}</span>'
            f'<span style="color:#C4CCD8;margin-left:4px">{chevron}</span>'
            '</div></div>'
        )
    return (
        '<div class="gg-card" style="padding:22px 24px">'
        '<div style="font-size:15px;font-weight:800;color:#1B2533">검진 기록</div>'
        f'<div>{rows}</div></div>'
    )


def dashboard_comparison_html(latest: dict, prev: dict) -> str:
    """전회 검진 대비 정상·주의·이상 변화 카드."""
    prev_date = prev["analyzed_at"].strftime("%Y. %m. %d")

    rows_data = [
        ("정상", prev["normal_count"],  latest["normal_count"],  True),
        ("주의", prev["caution_count"], latest["caution_count"], False),
        ("이상", prev["abnormal_count"],latest["abnormal_count"],False),
    ]

    total_prev = prev["normal_count"] + prev["caution_count"] + prev["abnormal_count"]
    total_curr = latest["normal_count"] + latest["caution_count"] + latest["abnormal_count"]
    score_prev = round(prev["normal_count"] / total_prev * 100) if total_prev else 0
    score_curr = round(latest["normal_count"] / total_curr * 100) if total_curr else 0
    score_delta = score_curr - score_prev

    if score_delta > 0:
        trend_label, trend_color, trend_bg = "전반적 개선", "#059669", "#ECFDF5"
    elif score_delta < 0:
        trend_label, trend_color, trend_bg = "전반적 악화", "#DC2626", "#FEF2F2"
    else:
        trend_label, trend_color, trend_bg = "변화 없음", "#64748B", "#F8FAFC"

    arrow_up = (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="18 15 12 9 6 15"/></svg>'
    )
    arrow_down = (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="6 9 12 15 18 9"/></svg>'
    )
    arrow_flat = (
        '<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">'
        '<line x1="5" y1="12" x2="19" y2="12"/></svg>'
    )

    def row(label, v_prev, v_curr, higher_is_better):
        delta = v_curr - v_prev
        if delta == 0:
            icon, d_color = arrow_flat, "#94A3B8"
        elif (delta > 0) == higher_is_better:
            icon, d_color = arrow_up, "#059669"
        else:
            icon, d_color = arrow_down if delta < 0 else arrow_up, "#DC2626"

        delta_str = f"+{delta}" if delta > 0 else str(delta)
        return (
            f'<div style="display:grid;grid-template-columns:56px 1fr auto auto;'
            f'align-items:center;gap:12px;padding:11px 0;border-top:1px solid #F1F5F9">'
            f'<div style="font-size:11.5px;font-weight:700;color:#94A3B8;letter-spacing:.2px">{label}</div>'
            f'<div style="display:flex;align-items:center;gap:8px">'
            f'<span style="font-size:20px;font-weight:800;color:#CBD5E1">{v_prev}</span>'
            f'<span style="color:#CBD5E1;font-size:11px">→</span>'
            f'<span style="font-size:20px;font-weight:800;color:#0D1117">{v_curr}</span>'
            f'</div>'
            f'<div style="display:flex;align-items:center;gap:4px;color:{d_color};font-size:12px;font-weight:700">'
            f'{icon}{delta_str}</div>'
            f'</div>'
        )

    rows_html = "".join(row(lb, vp, vc, hib) for lb, vp, vc, hib in rows_data)
    score_delta_str = f"+{score_delta}p" if score_delta > 0 else f"{score_delta}p" if score_delta < 0 else "±0p"

    return (
        '<div class="gg-card" style="padding:20px 22px">'
        '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:4px">'
        '<div>'
        '<div style="font-size:11px;font-weight:700;color:#94A3B8;letter-spacing:.5px;text-transform:uppercase">'
        '전회 대비 변화</div>'
        f'<div style="font-size:12px;color:#CBD5E1;margin-top:4px;font-weight:500">기준 {prev_date}</div>'
        '</div>'
        f'<div style="display:flex;align-items:center;gap:6px;background:{trend_bg};'
        f'border-radius:6px;padding:4px 10px">'
        f'<span style="font-size:11.5px;font-weight:700;color:{trend_color}">{trend_label}</span>'
        f'<span style="font-size:11px;color:{trend_color};font-weight:600">{score_delta_str}</span>'
        f'</div></div>'
        f'{rows_html}'
        '</div>'
    )


def tracked_html(tracked) -> str:
    rows = ""
    for t in tracked:
        s = STATUS[t["status"]]
        delta = str(t.get("delta", "-"))
        if delta != "-" and delta != "0" and delta != "+0.0" and delta != "-0.0":
            is_up = delta.startswith("+")
            d_color = "#D94F3A" if is_up else "#1F8A5B"
            d_icon = "↑" if is_up else "↓"
            delta_html = (
                f'<span style="font-size:12px;font-weight:700;color:{d_color};'
                f'background:{"#FBEAE8" if is_up else "#E7F5EE"};'
                f'border-radius:6px;padding:2px 7px">{d_icon} {delta.lstrip("+")}</span>'
            )
        else:
            delta_html = '<span style="font-size:11.5px;color:#C4CCD8;font-weight:500">전회 동일</span>'
        rows += (
            '<div style="display:flex;align-items:center;gap:13px;padding:14px 0;border-top:1px solid #F2F5F9">'
            f'<div style="width:42px;height:42px;flex:none;border-radius:12px;background:{s["bg"]};'
            f'display:flex;align-items:center;justify-content:center">'
            f'<div style="width:10px;height:10px;border-radius:50%;background:{s["color"]}"></div></div>'
            f'<div style="flex:1;min-width:0">'
            f'<div style="font-size:14px;font-weight:700;color:#1B2533">{t["name"]}</div>'
            f'<div style="font-size:11.5px;color:#9099A8;margin-top:3px">참조 {t["range"]}</div></div>'
            '<div style="text-align:right;flex:none">'
            f'<div style="font-size:17px;font-weight:800;color:{s["color"]}">{t["value"]}'
            f'<span style="font-size:11px;font-weight:500;color:#9099A8;margin-left:3px">{t["unit"]}</span></div>'
            f'<div style="margin-top:5px">{delta_html}</div></div></div>'
        )
    return (
        '<div class="gg-card" style="padding:22px 24px">'
        '<div style="font-size:15px;font-weight:800;color:#1B2533">추적 관찰 항목</div>'
        '<div style="font-size:12px;color:#9099A8;margin-top:3px;margin-bottom:4px">'
        '다음 검진 때 반드시 확인이 필요한 항목이에요</div>'
        f'<div>{rows}</div></div>'
    )


def next_checkup_html(next_date_str: str = "3개월 후", gcal_url: str = "") -> str:
    cal_icon = (
        '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        'stroke-width="2" stroke-linecap="round" stroke-linejoin="round">'
        '<rect x="3" y="4" width="18" height="18" rx="2"/>'
        '<line x1="16" y1="2" x2="16" y2="6"/><line x1="8" y1="2" x2="8" y2="6"/>'
        '<line x1="3" y1="10" x2="21" y2="10"/></svg>'
    )
    cal_btn = ""
    if gcal_url:
        cal_btn = (
            f'<a href="{gcal_url}" target="_blank" style="display:flex;align-items:center;'
            f'justify-content:center;gap:7px;margin-top:12px;background:#fff;'
            f'border:1px solid #CBD5E1;color:#0F3460;font-weight:700;font-size:13px;'
            f'border-radius:10px;padding:11px 16px;text-decoration:none">'
            f'{cal_icon} 구글 캘린더에 추가</a>'
        )
    return (
        '<div class="gg-card" style="padding:20px 22px">'
        '<div style="font-size:11px;font-weight:700;color:#94A3B8;letter-spacing:.5px;'
        'text-transform:uppercase;margin-bottom:12px">다음 검진 예정</div>'
        '<div style="background:#F8FAFC;border:1px solid #E2E8F0;border-radius:12px;padding:14px 16px">'
        '<div style="font-size:11px;font-weight:600;color:#94A3B8;letter-spacing:.3px;margin-bottom:6px">'
        '권장 재검 시기</div>'
        f'<div style="font-size:19px;font-weight:800;color:#0D1117;letter-spacing:-.3px;line-height:1.3">'
        f'{next_date_str}</div>'
        '<div style="font-size:12px;color:#94A3B8;margin-top:6px;line-height:1.6">'
        '주의·이상 항목의 변화 확인을 위한 권장 시점입니다.</div></div>'
        f'{cal_btn}</div>'
    )


def _line_icon(paths: str, size: int = 18) -> str:
    """공통 라인 아이콘 SVG (currentColor 상속)."""
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
        f'stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round">{paths}</svg>'
    )


# 메뉴 아이콘
_NAV_ICONS = {
    "grid": '<rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/>'
            '<rect x="14" y="14" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/>',
    "doc": '<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><path d="M14 2v6h6"/>',
    "chart": '<path d="M3 3v18h18"/><path d="M7 13l3-3 3 3 4-5"/>',
    "gear": '<circle cx="12" cy="12" r="3"/><path d="M19 12a7 7 0 0 0-.1-1l2-1.5-2-3.4-2.3 1a7 7 0 0 0-1.7-1l-.4-2.6h-4l-.4 2.6a7 7 0 0 0-1.7 1l-2.3-1-2 3.4 2 1.5a7 7 0 0 0 0 2l-2 1.5 2 3.4 2.3-1a7 7 0 0 0 1.7 1l.4 2.6h4l.4-2.6a7 7 0 0 0 1.7-1l2.3 1 2-3.4-2-1.5a7 7 0 0 0 .1-1z"/>',
    "check": '<rect x="3" y="3" width="18" height="18" rx="3"/><path d="M8 12l3 3 5-6"/>',
    "warn": '<path d="M12 3l9 16H3z"/><path d="M12 10v4"/><path d="M12 17h.01"/>',
}


def sidebar_nav_html(active: str) -> str:
    """대시보드 사이드바 메뉴 (라인 아이콘 + 활성 강조)."""
    items = [("dashboard", "grid", "대시보드"), ("records", "doc", "검진 기록"),
             ("track", "chart", "추적 관찰"), ("settings", "gear", "설정")]
    rows = ""
    for key, icon, label in items:
        on = key == active
        bg = "#EAF1FA" if on else "transparent"
        col = "#15448A" if on else "#6B7588"
        rows += (
            f'<div style="display:flex;align-items:center;gap:11px;color:{col};background:{bg};'
            f'font-weight:700;font-size:14px;padding:11px 12px;border-radius:10px;margin-bottom:3px">'
            f'{_line_icon(_NAV_ICONS[icon])}<span>{label}</span></div>'
        )
    return f"<div>{rows}</div>"


def sidebar_profile_html(name: str = "사용자", gender: str = "male", age: int = 0) -> str:
    """사이드바 하단 사용자 프로필 칩."""
    initial = name[0] if name else "U"
    gender_str = "남" if gender == "male" else "여"
    age_str = f"만 {age}세" if age else ""
    info = f"{gender_str} · {age_str}" if age_str else gender_str
    out_icon = _line_icon('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
                          '<path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>', 18)
    return (
        '<div style="display:flex;align-items:center;gap:11px;border-top:1px solid rgba(255,255,255,.10);'
        'padding:14px 4px 4px;color:#fff">'
        '<div style="width:36px;height:36px;flex:none;border-radius:50%;background:rgba(255,255,255,.16);color:#fff;'
        f'display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700">{initial}</div>'
        f'<div style="flex:1;min-width:0"><div style="font-size:13.5px;font-weight:700;color:#fff">{name}님</div>'
        f'<div style="font-size:11.5px;color:#B8C0CC;margin-top:1px">{info}</div></div>'
        f'<span style="color:#B8C0CC">{out_icon}</span></div>'
    )


def chatbot_hospital_prompt_html(location: str = "") -> str:
    """병원 추천을 독립 화면이 아닌 전역 챗봇 패널로 유도하는 카드."""
    location_text = location or "거주지 미설정"
    location_note = "현재 거주지 기준으로 추천할 수 있어요." if location else "설정에서 거주지를 입력하면 추천 정확도가 높아져요."
    return (
        '<div style="background:#fff;border:1px solid #E3E7EE;border-radius:18px;'
        'padding:18px 20px;margin-top:14px;box-shadow:0 7px 18px rgba(17,24,39,.05)">'
        '<div style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">'
        '<div>'
        '<div style="font-size:14.5px;font-weight:800;color:#182230">병원 추천은 AI 챗봇에서 이어집니다</div>'
        '<div style="font-size:13px;color:#475467;line-height:1.65;margin-top:8px">'
        '검진 결과를 보면서 진료과, 방문 우선순위, 주변 병원 추천을 대화형으로 확인할 수 있어요.</div>'
        f'<div style="font-size:12px;color:#667085;margin-top:10px">위치: {location_text} · {location_note}</div>'
        '</div>'
        '<div style="flex:none;background:#F8FAFC;border:1px solid #D7DEE8;border-radius:13px;'
        'padding:10px 12px;font-size:12px;font-weight:800;color:#173557">사이드바 AI 챗봇 열기</div>'
        '</div></div>'
    )


def fbs_chart_svg_html(trend) -> str:
    """주요 수치 추이 커스텀 SVG 차트 (영역 + 라인 + 정상 상한선 + 최신값)."""
    years, vals = trend["years"], trend["values"]
    nmax = trend.get("normal_max")
    W, H = 740, 300
    pad_l, pad_r, pad_t, pad_b = 28, 44, 44, 48
    # 동적 Y축 범위 — 정상 상한이 있으면 포함
    v_lo, v_hi = min(vals), max(vals)
    margin = (v_hi - v_lo) * 0.3 if v_hi != v_lo else max(abs(v_hi) * 0.12, 5)
    vmin = v_lo - margin
    vmax = v_hi + margin
    if nmax is not None:
        vmin = min(vmin, nmax - margin * 0.6)
        vmax = max(vmax, nmax + margin * 0.4)
    if vmax == vmin:
        vmax = vmin + 1
    n = len(vals)

    def cx(i):
        return pad_l + (W - pad_l - pad_r) * (i / (n - 1))

    def cy(v):
        return pad_t + (H - pad_t - pad_b) * (1 - (v - vmin) / (vmax - vmin))

    pts = [(cx(i), cy(v)) for i, v in enumerate(vals)]
    line_d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    base_y = cy(vmin)
    area_d = (f"M{pts[0][0]:.1f} {base_y:.1f} "
              + " ".join(f"L{x:.1f} {y:.1f}" for x, y in pts)
              + f" L{pts[-1][0]:.1f} {base_y:.1f} Z")
    mid_pts = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#fff" stroke="#15448A" stroke-width="3"/>'
                      for x, y in pts[:-1])
    lx, ly = pts[-1]
    year_labels = "".join(
        f'<text x="{cx(i):.1f}" y="{H - 14}" text-anchor="middle" font-size="15" font-weight="700" '
        f'fill="{"#B26A00" if i == n - 1 else "#9099A8"}">{years[i]}</text>' for i in range(n))
    ref_line = ""
    if nmax is not None:
        y_n = cy(nmax)
        ref_line = (
            f'<line x1="{pad_l}" x2="{W - pad_r}" y1="{y_n:.1f}" y2="{y_n:.1f}" stroke="#E0982E" '
            'stroke-width="1.6" stroke-dasharray="6 5"/>'
            f'<text x="{W - pad_r}" y="{y_n - 9:.1f}" text-anchor="end" font-size="13.5" font-weight="700" '
            f'fill="#B26A00">정상 상한 {nmax}</text>'
        )
    return (
        f'<svg viewBox="0 0 {W} {H}" width="100%" style="display:block">'
        '<defs><linearGradient id="fbsg" x1="0" x2="0" y1="0" y2="1">'
        '<stop offset="0" stop-color="#15448A" stop-opacity="0.16"/>'
        '<stop offset="1" stop-color="#15448A" stop-opacity="0"/></linearGradient></defs>'
        f'<path d="{area_d}" fill="url(#fbsg)"/>'
        f'{ref_line}'
        f'<path d="{line_d}" fill="none" stroke="#15448A" stroke-width="3" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        f'{mid_pts}'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="9" fill="#E0982E"/>'
        f'<text x="{lx:.1f}" y="{ly - 18:.1f}" text-anchor="middle" font-size="27" font-weight="800" '
        f'fill="#15448A">{vals[-1]}</text>'
        f'{year_labels}</svg>'
    )


def _track_chart_svg(dates: list, values: list, color: str, idx: int = 0) -> str:
    """추적 관찰 SVG 라인 차트 헬퍼 (area fill + dots + x-labels)."""
    W, H = 600, 150
    pad_l, pad_r, pad_t, pad_b = 8, 8, 18, 32
    n = len(values)
    grad_id = f"trkg{idx}"

    v_lo, v_hi = min(values), max(values)
    margin = (v_hi - v_lo) * 0.3 if v_hi != v_lo else max(abs(v_hi) * 0.15, 5)
    vmin = v_lo - margin
    vmax = v_hi + margin
    if vmax == vmin:
        vmax = vmin + 1

    def cx(i):
        return pad_l + (W - pad_l - pad_r) * (i / (n - 1))

    def cy(v):
        return pad_t + (H - pad_t - pad_b) * (1 - (v - vmin) / (vmax - vmin))

    pts = [(cx(i), cy(v)) for i, v in enumerate(values)]
    line_d = "M" + " L".join(f"{x:.1f} {y:.1f}" for x, y in pts)
    base_y = H - pad_b
    area_d = (
        f"M{pts[0][0]:.1f} {base_y:.1f} "
        + " ".join(f"L{x:.1f} {y:.1f}" for x, y in pts)
        + f" L{pts[-1][0]:.1f} {base_y:.1f} Z"
    )
    mid_dots = "".join(
        f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="#fff" stroke="{color}" stroke-width="2.2"/>'
        for x, y in pts[:-1]
    )
    lx, ly = pts[-1]
    year_labels = "".join(
        f'<text x="{cx(i):.1f}" y="{H - 8}" text-anchor="middle" '
        f'font-size="13" font-weight="{"700" if i == n - 1 else "500"}" '
        f'fill="{"#475569" if i == n - 1 else "#CBD5E1"}">{dates[i]}</text>'
        for i in range(n)
    )
    return (
        f'<svg viewBox="0 0 {W} {H}" width="100%" style="display:block;overflow:visible">'
        f'<defs><linearGradient id="{grad_id}" x1="0" x2="0" y1="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.15"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/>'
        f'</linearGradient></defs>'
        f'<path d="{area_d}" fill="url(#{grad_id})"/>'
        f'<path d="{line_d}" fill="none" stroke="{color}" stroke-width="2.5" '
        f'stroke-linecap="round" stroke-linejoin="round"/>'
        f'{mid_dots}'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="7" fill="{color}"/>'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="3" fill="#fff"/>'
        f'{year_labels}'
        f'</svg>'
    )


def track_item_card_html(
    item_name: str,
    dates: list,
    values: list,
    unit: str = "",
    status: str = "주의",
    diff_str: str = "-",
    idx: int = 0,
) -> str:
    """추적 관찰 항목 카드 — 상태별 테마 + SVG 라인 차트."""
    _STATUS_THEME = {
        "정상": ("#059669", "#ECFDF5"),
        "주의": ("#D97706", "#FFFBEB"),
        "이상": ("#DC2626", "#FEF2F2"),
        "응급": ("#DC2626", "#FEF2F2"),
    }
    color, badge_bg = _STATUS_THEME.get(status, ("#15448A", "#EDF4FF"))

    trend_icon = (
        '<svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="#94A3B8" '
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
        '<polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/>'
        '<polyline points="17 6 23 6 23 12"/></svg>'
    )
    header = (
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:14px">'
        f'<div style="display:flex;align-items:center;gap:8px">'
        f'{trend_icon}'
        f'<div style="font-size:16px;font-weight:800;color:#0D1117;letter-spacing:-.2px">{item_name}</div>'
        f'</div>'
        f'<div style="display:flex;align-items:center;gap:6px">'
        f'<span style="font-size:10.5px;font-weight:700;color:{color};background:{badge_bg};'
        f'border-radius:5px;padding:2px 8px;letter-spacing:.1px">{status}</span>'
        f'<span style="font-size:11px;color:#94A3B8;font-weight:500">{unit}</span>'
        f'</div></div>'
    )

    n = len(values)
    if n >= 2:
        chart_svg = _track_chart_svg(dates, values, color, idx)
        _neutral = {"-", "0", "+0.0", "-0.0", "+0", "0.0"}
        if diff_str not in _neutral:
            is_up = diff_str.startswith("+")
            d_color = "#D94F3A" if is_up else "#1F8A5B"
            d_bg = "#FBEAE8" if is_up else "#E7F5EE"
            arr_up = (
                '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
                '<polyline points="18 15 12 9 6 15"/></svg>'
            )
            arr_dn = (
                '<svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" '
                'stroke-width="3" stroke-linecap="round" stroke-linejoin="round">'
                '<polyline points="6 9 12 15 18 9"/></svg>'
            )
            d_icon = arr_up if is_up else arr_dn
            diff_html = (
                f'<span style="display:inline-flex;align-items:center;gap:4px;font-size:12px;'
                f'font-weight:700;color:{d_color};background:{d_bg};'
                f'border-radius:6px;padding:3px 8px">'
                f'{d_icon}{diff_str.lstrip("+")}</span>'
            )
        else:
            diff_html = '<span style="font-size:11.5px;color:#CBD5E1;font-weight:500">전회 동일</span>'

        footer = (
            f'<div style="display:flex;align-items:baseline;gap:8px;margin-top:12px;'
            f'padding-top:12px;border-top:1px solid #F1F5F9">'
            f'<span style="font-size:28px;font-weight:800;color:{color};letter-spacing:-.5px;line-height:1">'
            f'{values[-1]}</span>'
            f'<span style="font-size:12px;color:#94A3B8;font-weight:500">{unit}</span>'
            f'<span style="margin-left:auto">{diff_html}</span>'
            f'</div>'
        )
        body = f'{chart_svg}{footer}'
    elif n == 1:
        body = (
            f'<div style="padding:20px 0 8px">'
            f'<div style="font-size:36px;font-weight:800;color:{color};letter-spacing:-.5px;line-height:1">'
            f'{values[0]}'
            f'<span style="font-size:14px;color:#94A3B8;font-weight:500;margin-left:6px">{unit}</span></div>'
            f'<div style="font-size:12.5px;color:#94A3B8;margin-top:12px;line-height:1.6">'
            f'2회 이상 검진 기록이 있어야 변화 추이를 확인할 수 있어요.</div>'
            f'</div>'
        )
    else:
        body = '<div style="font-size:13px;color:#CBD5E1;padding:20px 0">이 항목의 이력이 없어요.</div>'

    return (
        '<div class="gg-card" style="padding:20px 22px">'
        f'{header}{body}'
        '</div>'
    )


def feature_cards_html() -> str:
    """업로드 화면 하단 기능 소개 3카드."""
    cards = [
        ("check", "#15448A", "근거 기반 해석", "공인 의료 기준을 인용해 환각·과잉진단 억제합니다"),
        ("warn", "#B26A00", "주의 항목 자동 표시", "정상 범위를 벗어난 항목을 한눈에 하이라이트합니다"),
        ("chart", "#1F8A5B", "추적 권장 정리", "다음 검진 때 확인할 항목을 모아 관리해 드립니다"),
    ]
    out = ""
    for icon, color, title, desc in cards:
        out += (
            '<div style="flex:1;background:#fff;border:1px solid #E4E9F0;border-radius:16px;padding:20px">'
            f'<div style="color:{color}">{_line_icon(_NAV_ICONS[icon], 22)}</div>'
            f'<div style="font-size:14.5px;font-weight:800;margin-top:12px;color:#1B2533">{title}</div>'
            f'<div style="font-size:12.5px;color:#7B8597;margin-top:7px;line-height:1.6">{desc}</div></div>'
        )
    return f'<div style="display:flex;gap:14px;margin-top:18px">{out}</div>'


def brand_panel_html() -> str:
    """로그인/회원가입 좌측 split-screen 패널 — 앱 로고 + 브랜드 카피."""
    logo_el = brand_lockup_html(icon_width=144, logo_width=300, gap=14)

    features = [
        ("공인 의료 기준 근거로 항목별 자동 해석", "#4ADE80"),
        ("주의·이상 수치를 한눈에 하이라이트", "#60A5FA"),
        ("추적 항목 자동 선정 및 재검 일정 안내", "#FACC15"),
    ]
    feat_rows = "".join(
        f'<div style="display:flex;align-items:flex-start;gap:12px;margin-top:14px">'
        f'<span style="width:5px;height:5px;border-radius:50%;background:{c};'
        f'flex:none;margin-top:7px"></span>'
        f'<span style="font-size:13.5px;color:#D4DBE6;line-height:1.6">{t}</span></div>'
        for t, c in features
    )

    # 배경 심전도 장식선
    deco = (
        '<svg viewBox="0 0 600 240" preserveAspectRatio="xMidYMax meet" '
        'style="position:absolute;left:0;right:0;bottom:0;width:100%;height:44%;'
        'opacity:.10;pointer-events:none">'
        '<path d="M0 158 H210 l24 0 22 -86 26 150 22 -120 18 78 20 0 H600" '
        'fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
        '<circle cx="500" cy="140" r="130" fill="none" stroke="#fff" stroke-width="1.2"/>'
        '</svg>'
    )

    return (
        '<div class="gg-auth-brand-panel" style="position:fixed;top:0;left:0;bottom:0;width:26vw;'
        'z-index:5;overflow:hidden;'
        'background:linear-gradient(160deg,#1A2E48 0%,#0F1E30 50%,#09141F 100%);'
        'color:#fff;padding:52px 44px;display:flex;flex-direction:column">'
        f'{deco}'
        '<div style="position:relative;z-index:1;display:flex;flex-direction:column;flex:1">'

        # 로고 블록
        f'<div style="display:flex;align-items:center;max-width:100%">'
        f'{logo_el}'
        f'</div>'

        # 메인 카피
        '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">'
        '<div style="font-size:11px;font-weight:700;letter-spacing:2px;color:#6B8AAA;'
        'text-transform:uppercase;margin-bottom:16px">AI Health Report Workspace</div>'
        '<div style="font-size:30px;font-weight:800;letter-spacing:-.8px;line-height:1.35;'
        'word-break:keep-all">'
        '검진 결과를 읽고,<br>다음 액션까지<br>이어집니다</div>'
        '<div style="font-size:13.5px;line-height:1.75;color:#8CA3BF;margin-top:18px;word-break:keep-all">'
        '수치 해석에서 끝나지 않고, 관리 항목·추적 변화·병원 상담 흐름까지 한 화면에 정리합니다.'
        '</div></div>'

        # 기능 목록
        f'<div style="border-top:1px solid rgba(255,255,255,.08);padding-top:22px">{feat_rows}</div>'

        '</div></div>'
    )
