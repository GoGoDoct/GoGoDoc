# -*- coding: utf-8 -*-
"""HTML 렌더 헬퍼. st.markdown(..., unsafe_allow_html=True) 로 출력할 문자열을 만든다.

Streamlit 마크다운은 들여쓰기 4칸을 코드블록으로 해석하므로,
여기서 만드는 HTML 문자열은 줄 앞 공백 없이 한 줄로 합쳐서 반환한다.
"""
from sample_data import STATUS, range_text, bar_metrics


def _val_label(it):
    return it.get("value_text", it["value"])


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
    border = "#E4E9F0" if it["status"] == "정상" else s["border"]
    return (
        f'<div class="gg-card" style="border-color:{border}">'
        f'<div class="gg-pad">'
        # 헤더
        f'<div style="display:flex;align-items:center;justify-content:space-between;gap:12px">'
        f'<div style="display:flex;align-items:center;gap:9px;min-width:0">'
        f'<span class="gg-tag">{it["cat"]}</span>'
        f'<span style="font-size:14.5px;font-weight:700;color:#2B3545">{it["name"]}</span>'
        f'</div>'
        f'<span class="gg-pill" style="color:{s["color"]};background:{s["bg"]}">'
        f'<span class="gg-dot" style="background:{s["color"]}"></span>{it["status"]}</span>'
        f'</div>'
        # 값
        f'<div style="display:flex;align-items:baseline;gap:8px;margin-top:12px">'
        f'<span style="font-size:26px;font-weight:800;color:{s["color"]};line-height:1">{_val_label(it)}</span>'
        f'<span style="font-size:13px;color:#9099A8;font-weight:500">{it["unit"]}</span>'
        f'<span style="font-size:12px;color:#A4ACBA;margin-left:auto">참조 {range_text(it)}</span>'
        f'</div>'
        f'{bar_html(it)}'
        f'</div>'
        # 쉬운 설명 (네이티브 <details>)
        f'<details class="gg-details"><summary>쉬운 설명 보기</summary>'
        f'<div class="gg-explain"><div class="box">'
        f'<div style="font-size:13px;line-height:1.7;color:#3C4656">{it["explain"]}</div>'
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


def disclaimer_html() -> str:
    return (
        '<div style="display:flex;gap:10px;background:#FBFCFE;border:1px solid #E4E9F0;'
        'border-radius:12px;padding:14px 16px;margin-top:12px">'
        '<span style="color:#8590A1;font-weight:700">ⓘ</span>'
        '<div style="font-size:11.5px;line-height:1.65;color:#7B8597">본 해석은 공인 의료 기준을 근거로 한 '
        '<b style="color:#5B6678">참고용 정보이며 의료 진단이 아닙니다.</b> '
        '정확한 진단과 치료는 반드시 의료진과 상담하시기 바랍니다.</div></div>'
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
    def pill(n, label, color, bg, border):
        return (
            f'<div style="text-align:center;min-width:62px;background:{bg};border:1px solid {border};'
            f'border-radius:11px;padding:8px 12px">'
            f'<div style="font-size:20px;font-weight:800;color:{color};line-height:1">{n}</div>'
            f'<div style="font-size:11px;color:{color};margin-top:4px;font-weight:600">{label}</div></div>'
        )
    return (
        '<div style="display:flex;gap:9px;justify-content:flex-end">'
        + pill(normal, "정상", "#1F8A5B", "#E7F5EE", "#CDEBDB")
        + pill(caution, "주의", "#B26A00", "#FBF1E0", "#F2DFB8")
        + pill(abnormal, "이상", "#C0392B", "#FBEAE8", "#F3CFCB")
        + '</div>'
    )


# ── 대시보드 ──────────────────────────────────────────
def kpi_cards_html(manage, normal, caution, abnormal) -> str:
    def small(label, val, color, sub):
        return (
            f'<div style="flex:1;background:#fff;border:1px solid #E4E9F0;border-radius:16px;padding:18px">'
            f'<div style="font-size:13px;color:#7B8597;font-weight:600">{label}</div>'
            f'<div style="font-size:30px;font-weight:800;color:{color};margin-top:8px;line-height:1">{val}</div>'
            f'<div style="font-size:12px;color:#A4ACBA;margin-top:8px">{sub}</div></div>'
        )
    big = (
        '<div style="flex:1.5;background:linear-gradient(150deg,#1B5AA8,#103A74);color:#fff;'
        'border-radius:16px;padding:20px 22px;box-shadow:0 8px 22px rgba(16,54,110,.22)">'
        '<div style="font-size:13px;opacity:.85;font-weight:600">관리가 필요한 항목</div>'
        f'<div style="display:flex;align-items:baseline;gap:6px;margin-top:10px">'
        f'<span style="font-size:38px;font-weight:800;line-height:1">{manage}</span>'
        '<span style="font-size:15px;opacity:.85">개 항목</span></div>'
        '<div style="font-size:12.5px;opacity:.82;margin-top:8px;line-height:1.5">'
        '주의 7 · 이상 1 — 생활습관 관리로 개선 가능한 단계예요.</div></div>'
    )
    return (
        '<div style="display:flex;gap:14px;margin-top:22px">'
        + big
        + small("정상", normal, "#1F8A5B", "전체 12개 중")
        + small("주의", caution, "#B26A00", "추적 권장")
        + small("이상", abnormal, "#C0392B", "재검 필요")
        + '</div>'
    )


def records_html(records) -> str:
    rows = ""
    doc_icon = _line_icon('<path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>'
                          '<path d="M14 2v6h6"/>', 18)
    chevron = _line_icon('<path d="M9 18l6-6-6-6"/>', 18)
    for r in records:
        # 상태별 아이콘 색조 (이상>주의>정상 우선)
        if r["abnormal"]:
            ic_col, ic_bg = "#C0392B", "#FBEAE8"
        elif r["caution"]:
            ic_col, ic_bg = "#B26A00", "#FBF1E0"
        else:
            ic_col, ic_bg = "#1F8A5B", "#E7F5EE"
        rows += (
            '<div style="display:flex;align-items:center;gap:14px;padding:13px 0;border-top:1px solid #F2F5F9">'
            f'<div style="width:42px;height:42px;flex:none;border-radius:11px;background:{ic_bg};color:{ic_col};'
            f'display:flex;align-items:center;justify-content:center">{doc_icon}</div>'
            f'<div style="flex:1;min-width:0"><div style="font-size:14px;font-weight:700">{r["title"]}</div>'
            f'<div style="font-size:12px;color:#8590A1;margin-top:3px">{r["date"]} · {r["center"]}</div></div>'
            '<div style="display:flex;gap:6px;flex:none;align-items:center">'
            f'<span style="font-size:11.5px;font-weight:700;color:#1F8A5B;background:#E7F5EE;border-radius:7px;padding:3px 8px">정상 {r["normal"]}</span>'
            f'<span style="font-size:11.5px;font-weight:700;color:#B26A00;background:#FBF1E0;border-radius:7px;padding:3px 8px">주의 {r["caution"]}</span>'
            f'<span style="font-size:11.5px;font-weight:700;color:#C0392B;background:#FBEAE8;border-radius:7px;padding:3px 8px">이상 {r["abnormal"]}</span>'
            f'<span style="color:#C4CCD8;margin-left:4px">{chevron}</span>'
            '</div></div>'
        )
    return (
        '<div class="gg-card" style="padding:22px 24px">'
        '<div style="font-size:15px;font-weight:800">검진 기록</div>'
        f'<div style="margin-top:8px">{rows}</div></div>'
    )


def tracked_html(tracked) -> str:
    rows = ""
    for t in tracked:
        s = STATUS[t["status"]]
        rows += (
            '<div style="display:flex;align-items:center;gap:12px;padding:12px 0;border-top:1px solid #F2F5F9">'
            f'<span class="gg-dot" style="background:{s["color"]}"></span>'
            f'<div style="flex:1;min-width:0"><div style="font-size:13.5px;font-weight:700">{t["name"]}</div>'
            f'<div style="font-size:11.5px;color:#9099A8;margin-top:2px">참조 {t["range"]}</div></div>'
            '<div style="text-align:right;flex:none">'
            f'<div style="font-size:15px;font-weight:800;color:{s["color"]}">{t["value"]} '
            f'<span style="font-size:10.5px;font-weight:500;color:#9099A8">{t["unit"]}</span></div>'
            f'<div style="font-size:11px;color:#C0392B;margin-top:2px;font-weight:600">▲ {t["delta"]}</div></div></div>'
        )
    return (
        '<div class="gg-card" style="padding:22px 24px">'
        '<div style="display:flex;align-items:center;justify-content:space-between">'
        '<div style="font-size:15px;font-weight:800">추적 관찰 항목</div>'
        '<span style="font-size:12px;color:#15448A;font-weight:700">전체보기</span></div>'
        f'<div style="margin-top:6px">{rows}</div></div>'
    )


def next_checkup_html() -> str:
    return (
        '<div class="gg-card" style="padding:22px 24px">'
        '<div style="font-size:15px;font-weight:800">📅 다음 검진 예정</div>'
        '<div style="margin-top:14px;background:#F8FAFC;border-radius:12px;padding:15px">'
        '<div style="font-size:13px;color:#7B8597">권장 재검 시기</div>'
        '<div style="font-size:19px;font-weight:800;color:#15448A;margin-top:5px">2026년 9월 (3개월 후)</div>'
        '<div style="font-size:12px;color:#8590A1;margin-top:6px;line-height:1.5">'
        '주의·이상 항목의 변화를 확인하기 위한 권장 시점이에요.</div></div>'
        '<div style="margin-top:13px;text-align:center;border:1px solid #15448A;color:#15448A;'
        'font-weight:700;font-size:13.5px;border-radius:11px;padding:11px;cursor:pointer">캘린더에 추가</div></div>'
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


def sidebar_profile_html() -> str:
    """사이드바 하단 사용자 프로필 칩."""
    out_icon = _line_icon('<path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/>'
                          '<path d="M16 17l5-5-5-5"/><path d="M21 12H9"/>', 18)
    return (
        '<div style="display:flex;align-items:center;gap:11px;border-top:1px solid #EDF1F6;'
        'padding:14px 4px 4px">'
        '<div style="width:36px;height:36px;flex:none;border-radius:50%;background:#15448A;color:#fff;'
        'display:flex;align-items:center;justify-content:center;font-size:14px;font-weight:700">홍</div>'
        '<div style="flex:1;min-width:0"><div style="font-size:13.5px;font-weight:700;color:#1B2533">홍길동님</div>'
        '<div style="font-size:11.5px;color:#8590A1;margin-top:1px">남 · 만 40세</div></div>'
        f'<span style="color:#9099A8">{out_icon}</span></div>'
    )


def fbs_chart_svg_html(trend) -> str:
    """공복혈당 추이 커스텀 SVG 차트 (영역 + 라인 + 정상 상한 + 최신값)."""
    years, vals, nmax = trend["years"], trend["values"], trend["normal_max"]
    W, H = 740, 300
    pad_l, pad_r, pad_t, pad_b = 28, 44, 44, 48
    vmin, vmax = 90, 112
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
    y_n = cy(nmax)
    mid_pts = "".join(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6" fill="#fff" stroke="#15448A" stroke-width="3"/>'
                      for x, y in pts[:-1])
    lx, ly = pts[-1]
    year_labels = "".join(
        f'<text x="{cx(i):.1f}" y="{H - 14}" text-anchor="middle" font-size="15" font-weight="700" '
        f'fill="{"#B26A00" if i == n - 1 else "#9099A8"}">{years[i]}</text>' for i in range(n))
    return (
        f'<svg viewBox="0 0 {W} {H}" width="100%" style="display:block">'
        '<defs><linearGradient id="fbsg" x1="0" x2="0" y1="0" y2="1">'
        '<stop offset="0" stop-color="#15448A" stop-opacity="0.16"/>'
        '<stop offset="1" stop-color="#15448A" stop-opacity="0"/></linearGradient></defs>'
        f'<path d="{area_d}" fill="url(#fbsg)"/>'
        f'<line x1="{pad_l}" x2="{W - pad_r}" y1="{y_n:.1f}" y2="{y_n:.1f}" stroke="#E0982E" '
        'stroke-width="1.6" stroke-dasharray="6 5"/>'
        f'<text x="{W - pad_r}" y="{y_n - 9:.1f}" text-anchor="end" font-size="13.5" font-weight="700" '
        f'fill="#B26A00">정상 상한 {nmax}</text>'
        f'<path d="{line_d}" fill="none" stroke="#15448A" stroke-width="3" stroke-linecap="round" '
        'stroke-linejoin="round"/>'
        f'{mid_pts}'
        f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="9" fill="#E0982E"/>'
        f'<text x="{lx:.1f}" y="{ly - 18:.1f}" text-anchor="middle" font-size="27" font-weight="800" '
        f'fill="#15448A">{vals[-1]}</text>'
        f'{year_labels}</svg>'
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
    """로그인/회원가입 좌측 딥블루 패널."""
    points = [
        "공인 의료 기준 근거 기반 해석",
        "주의·이상 항목 자동 하이라이트",
        "업로드 즉시 삭제 · 서버 미저장",
    ]
    pts = "".join(
        f'<div style="display:flex;align-items:center;gap:11px;font-size:14px;opacity:.92;margin-top:13px">'
        f'<span style="width:22px;height:22px;flex:none;border-radius:50%;background:rgba(255,255,255,.16);'
        f'display:flex;align-items:center;justify-content:center;font-size:12px">✓</span>{p}</div>'
        for p in points
    )
    # 로고 펄스(심전도) 아이콘
    logo_icon = (
        '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="#fff" '
        'stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">'
        '<path d="M3 12h4l2.5 7 4-14 2.5 7H21"/></svg>'
    )
    # 하단 배경 심전도 그래픽 (저채도)
    deco = (
        '<svg viewBox="0 0 600 240" preserveAspectRatio="xMidYMax meet" '
        'style="position:absolute;left:0;right:0;bottom:0;width:100%;height:46%;opacity:.13;pointer-events:none">'
        '<circle cx="470" cy="150" r="118" fill="none" stroke="#fff" stroke-width="1.4"/>'
        '<path d="M0 158 H210 l24 0 22 -86 26 150 22 -120 18 78 20 0 H600" '
        'fill="none" stroke="#fff" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round"/></svg>'
    )
    return (
        '<div style="position:fixed;top:0;left:0;bottom:0;width:26vw;z-index:5;overflow:hidden;'
        'background:linear-gradient(160deg,#1B5AA8 0%,#103A74 60%,#0C2D5C 100%);color:#fff;'
        'padding:48px 44px;display:flex;flex-direction:column">'
        f'{deco}'
        '<div style="position:relative;z-index:1;display:flex;flex-direction:column;flex:1;height:100%">'
        '<div style="display:flex;align-items:center;gap:12px">'
        '<div style="width:44px;height:44px;border-radius:12px;background:rgba(255,255,255,.16);'
        f'display:flex;align-items:center;justify-content:center">{logo_icon}</div>'
        '<div style="font-size:21px;font-weight:800">GoGoDoc</div></div>'
        '<div style="flex:1;display:flex;flex-direction:column;justify-content:center">'
        '<div style="font-size:13px;font-weight:600;letter-spacing:2px;opacity:.7">AI 검진 해석 비서</div>'
        '<div style="font-size:34px;font-weight:800;letter-spacing:-1px;line-height:1.3;margin-top:16px">'
        '어려운 검진 수치,<br>쉬운 말로 풀어드려요</div>'
        '<div style="font-size:15px;line-height:1.7;opacity:.82;margin-top:18px">'
        '결과지를 올리면 신경 써야 할 항목과 추적할 항목을 정리해 드립니다. 매년 받는 검진, 이제 제대로 이해하세요.</div></div>'
        f'<div>{pts}</div></div></div>'
    )
