# -*- coding: utf-8 -*-
"""샘플 데이터 + 항목 해설 딕셔너리.

기획서 4.1 파이프라인 ②③에서 쓰는 '항목별 정상범위·해설·주의사항' 사전을
여기서 고정한다. 실제 서비스에서는 D1 단계에 PubMed / ICD-10 MCP 근거로
보강한 dict를 이 자리에 둔다.
"""

# 상태별 색상 (정상/주의/이상/응급) — 디자인 시스템과 동일
STATUS = {
    "정상": {"color": "#1F8A5B", "bg": "#E7F5EE", "bar": "#2BAE72", "border": "#E4E9F0"},
    "주의": {"color": "#B26A00", "bg": "#FBF1E0", "bar": "#E0982E", "border": "#F2DFB8"},
    "이상": {"color": "#C0392B", "bg": "#FBEAE8", "bar": "#D9534F", "border": "#F3CFCB"},
    "응급": {"color": "#B02A20", "bg": "#FBE7E5", "bar": "#B02A20", "border": "#E9B7B2"},
}

# 검사 항목 (저장 키: 항목, 값, 단위, 참조범위 low/high, 상태, 해설, 근거)
# low=0 → 'high 이하', high=None → 'low 이상'
SAMPLE_ITEMS = [
    {"id": "ast", "cat": "간기능", "name": "AST(GOT)", "value": 28, "unit": "U/L",
     "low": 0, "high": 40, "status": "정상", "source": "대한임상검사정도관리협회",
     "explain": "간세포가 손상되면 혈액으로 새어 나오는 효소예요. 현재 정상 범위 안이라 간 손상 신호는 보이지 않습니다."},
    {"id": "alt", "cat": "간기능", "name": "ALT(GPT)", "value": 52, "unit": "U/L",
     "low": 0, "high": 40, "status": "주의", "source": "질병관리청 국가건강정보포털",
     "explain": "간 손상에 더 민감한 효소로, 기준(40)보다 약간 높아요. 지방간·과음·피로 등을 점검하고 생활습관을 관리하면 좋아요."},
    {"id": "ggt", "cat": "간기능", "name": "γ-GTP", "value": 88, "unit": "U/L",
     "low": 11, "high": 63, "status": "이상", "source": "건강보험심사평가원",
     "explain": "음주·담도 이상에서 잘 오르는 수치예요. 기준을 넘어 추적 관찰이 필요하며, 절주 후 재검을 권장합니다."},
    {"id": "fbs", "cat": "당대사", "name": "공복혈당", "value": 108, "unit": "mg/dL",
     "low": 70, "high": 99, "status": "주의", "source": "대한당뇨병학회 진료지침",
     "explain": "공복 혈당이 기준(99)보다 약간 높은 '공복혈당장애' 경계예요. 식이·운동 관리로 되돌릴 수 있는 단계입니다."},
    {"id": "hba1c", "cat": "당대사", "name": "당화혈색소", "value": 5.9, "unit": "%",
     "low": 4.0, "high": 5.6, "status": "주의", "source": "대한당뇨병학회 진료지침",
     "explain": "지난 2~3개월의 평균 혈당이에요. 당뇨 전단계 범위에 들어 식습관 관리가 권장됩니다."},
    {"id": "tc", "cat": "지질", "name": "총콜레스테롤", "value": 215, "unit": "mg/dL",
     "low": 0, "high": 199, "status": "주의", "source": "질병관리청 국가건강정보포털",
     "explain": "혈중 전체 콜레스테롤이 기준보다 높아요. 포화지방 섭취를 줄이고 활동량을 늘리는 것이 도움이 됩니다."},
    {"id": "ldl", "cat": "지질", "name": "LDL 콜레스테롤", "value": 142, "unit": "mg/dL",
     "low": 0, "high": 129, "status": "주의", "source": "한국지질·동맥경화학회",
     "explain": "'나쁜' 콜레스테롤로, 기준보다 높으면 혈관 벽에 쌓일 수 있어요. 식이·운동 관리가 필요합니다."},
    {"id": "hdl", "cat": "지질", "name": "HDL 콜레스테롤", "value": 55, "unit": "mg/dL",
     "low": 40, "high": None, "status": "정상", "source": "한국지질·동맥경화학회",
     "explain": "'좋은' 콜레스테롤이에요. 기준 이상으로 혈관 건강에 도움이 되는 양호한 수치입니다."},
    {"id": "tg", "cat": "지질", "name": "중성지방", "value": 178, "unit": "mg/dL",
     "low": 0, "high": 149, "status": "주의", "source": "한국지질·동맥경화학회",
     "explain": "에너지로 쓰이고 남은 지방이에요. 기준보다 높아 단 음식·음주·탄수화물 섭취 조절이 권장됩니다."},
    {"id": "bp", "cat": "기타", "name": "혈압(수축기/이완기)", "value": 138, "value_text": "138/88",
     "unit": "mmHg", "low": 0, "high": 129, "status": "주의", "source": "대한고혈압학회 진료지침",
     "explain": "138/88로 '고혈압 전단계'에 해당해요. 저염식·규칙적 운동과 함께 가정에서 재측정을 권장합니다."},
    {"id": "hb", "cat": "기타", "name": "혈색소", "value": 15.2, "unit": "g/dL",
     "low": 13, "high": 17, "status": "정상", "source": "대한진단검사의학회",
     "explain": "산소를 운반하는 적혈구 색소예요. 정상 범위로 빈혈 징후는 보이지 않습니다."},
    {"id": "cr", "cat": "신장", "name": "크레아티닌", "value": 0.95, "unit": "mg/dL",
     "low": 0.7, "high": 1.3, "status": "정상", "source": "대한신장학회",
     "explain": "콩팥이 노폐물을 잘 거르는지 보는 지표예요. 정상 범위로 신장 기능은 양호합니다."},
]

# 응급(패닉밸류) 시나리오용 항목 — 기획서 5장 가드레일
EMERGENCY_ITEM = {
    "id": "emg", "cat": "당대사", "name": "공복혈당 (재측정)", "value": 520, "unit": "mg/dL",
    "low": 70, "high": 99, "status": "응급", "source": "응급 패닉밸류 기준 (≥500)",
    "explain": "혈당이 응급 기준(500 mg/dL)을 초과했습니다. 지체 없이 가까운 응급실 또는 의료기관에 내원하세요. "
               "이는 즉각적인 처치가 필요한 위험 수치입니다.",
}

# 대시보드용 — 검진 기록 / 추적 항목 / 추이
RECORDS = [
    {"title": "종합건강검진", "date": "2026-06-10", "center": "한빛종합건강검진센터", "normal": 4, "caution": 7, "abnormal": 1},
    {"title": "종합건강검진", "date": "2025-05-22", "center": "한빛종합건강검진센터", "normal": 6, "caution": 5, "abnormal": 0},
    {"title": "종합건강검진", "date": "2024-06-03", "center": "서울365의원", "normal": 8, "caution": 3, "abnormal": 0},
    {"title": "일반건강검진", "date": "2023-05-18", "center": "서울365의원", "normal": 10, "caution": 1, "abnormal": 0},
]

TRACKED = [
    {"name": "공복혈당", "value": "108", "unit": "mg/dL", "range": "70~99", "status": "주의", "delta": "+4"},
    {"name": "LDL 콜레스테롤", "value": "142", "unit": "mg/dL", "range": "129 이하", "status": "주의", "delta": "+3"},
    {"name": "γ-GTP", "value": "88", "unit": "U/L", "range": "11~63", "status": "이상", "delta": "+12"},
    {"name": "ALT(GPT)", "value": "52", "unit": "U/L", "range": "40 이하", "status": "주의", "delta": "+6"},
    {"name": "혈압", "value": "138/88", "unit": "mmHg", "range": "129 이하", "status": "주의", "delta": "+2"},
]

FBS_TREND = {"years": ["2023", "2024", "2025", "2026"], "values": [96, 101, 104, 108], "normal_max": 99}


def range_text(item) -> str:
    low, high = item["low"], item["high"]
    if high is None:
        return f"{low} 이상"
    if low == 0:
        return f"{high} 이하"
    return f"{low}~{high}"


def bar_metrics(value, low, high):
    """값을 막대 위 위치(%)로 변환. 검진 결과 AI 해석.dc.html 과 동일 알고리즘."""
    lo, hi, v = low, high, value
    if lo is not None and hi not in (None, 0):
        w = (hi - lo) or hi
        dmin, dmax = lo - w * 0.6, hi + w * 0.6
    elif hi is not None:
        dmin, dmax, lo = 0, hi * 1.6, 0
    else:
        dmin, dmax = 0, (lo or v) * 1.8
        hi = dmax
    if dmin < 0 and (low is not None and low >= 0):
        dmin = 0
    span = (dmax - dmin) or 1
    clamp = lambda x: max(1.5, min(98.5, x))
    marker = clamp((v - dmin) / span * 100)
    n_left = max(0, min(100, (lo - dmin) / span * 100))
    n_right = max(0, min(100, (hi - dmin) / span * 100))
    return marker, n_left, max(0, n_right - n_left)
