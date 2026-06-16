"""항목별 임상 밴드 - 정상/주의/이상/응급 컷오프 (순수 도메인 규칙)

기존 일반 편차비율 모델(dev<=0.5->주의)이 항목별 임상 구간과 어긋나, 팀 공식 골든셋 기준의
명시적 컷오프로 분류한다. 규칙은 (연산자, 임계값, flag) 리스트로 위에서부터 첫 매칭(중증 우선),
미매칭 시 normal. 성별 의존 항목은 {male, female} dict.

⚠ 컷오프는 팀 골든셋(검수 필요 초안)·일반 통용 기준 기반 - 실서비스 전 공단·학회 검수 필수.
종양표지자(CEA/AFP/CA19-9/PSA)는 상승해도 '주의'까지만 - 단독 진단 의미 약함(과잉해석 방지).
밴드 미정의 항목은 classify 가 기존 범위·패닉 로직으로 폴백.
"""

# (op, threshold, flag) - op in ">=",">","<=","<"
BANDS: dict[str, list | dict] = {
    # 혈당
    "공복혈당": [(">=", 300, "emergency"), ("<=", 50, "emergency"),
                (">=", 126, "abnormal"), (">=", 100, "caution"), ("<", 70, "caution")],
    "당화혈색소": [(">=", 6.5, "abnormal"), (">=", 5.7, "caution")],
    # 혈압
    "수축기혈압": [(">=", 180, "emergency"), (">=", 140, "abnormal"), (">=", 121, "caution"), ("<", 90, "caution")],
    "이완기혈압": [(">=", 120, "emergency"), (">=", 90, "abnormal"), (">=", 81, "caution"), ("<", 60, "caution")],
    # 지질
    "총콜레스테롤": [(">=", 240, "abnormal"), (">=", 200, "caution")],
    "LDL 콜레스테롤": [(">=", 160, "abnormal"), (">=", 130, "caution")],
    "HDL 콜레스테롤": [("<", 30, "abnormal"), ("<", 40, "caution")],  # 낮을수록 나쁨
    "중성지방": [(">=", 200, "abnormal"), (">=", 150, "caution")],
    # 간
    "AST": [(">=", 80, "abnormal"), (">", 40, "caution")],
    "ALT": [(">=", 80, "abnormal"), (">", 40, "caution")],
    "감마지티피": {
        "male": [(">=", 126, "abnormal"), (">", 63, "caution")],
        "female": [(">=", 70, "abnormal"), (">", 35, "caution")],
    },
    # 신장
    "크레아티닌": {
        "male": [(">=", 7.0, "emergency"), (">=", 2.0, "abnormal"), (">", 1.3, "caution")],
        "female": [(">=", 7.0, "emergency"), (">=", 1.5, "abnormal"), (">", 1.0, "caution")],
    },
    "eGFR": [("<", 60, "abnormal"), ("<", 90, "caution")],  # 낮을수록 나쁨
    # 대사
    "요산": {
        "male": [(">=", 9.0, "abnormal"), (">", 7.0, "caution")],
        "female": [(">=", 8.0, "abnormal"), (">", 6.0, "caution")],
    },
    # 혈액 - 헤모글로빈 낮을수록 나쁨
    "헤모글로빈": {
        "male": [("<", 7.0, "emergency"), ("<", 10, "abnormal"), ("<", 13, "caution")],
        "female": [("<", 7.0, "emergency"), ("<", 10, "abnormal"), ("<", 12, "caution")],
    },
    # 계측
    "BMI": [(">=", 25, "abnormal"), (">=", 23, "caution"), ("<", 18.5, "caution")],
    # 갑상선 - 양방향
    "TSH": [("<=", 0.1, "abnormal"), (">", 4.0, "caution"), ("<", 0.4, "caution")],
    # 종양표지자 - 상승해도 주의까지만 (단독 진단 불가)
    "CEA": [(">", 5, "caution")],
    "AFP": [(">", 10, "caution")],
    "CA19-9": [(">", 37, "caution")],
    "PSA": [(">", 4, "caution")],
}

_OPS = {
    ">=": lambda v, t: v >= t,
    ">": lambda v, t: v > t,
    "<=": lambda v, t: v <= t,
    "<": lambda v, t: v < t,
}


def classify_band(canonical: str, value: float, sex: str) -> str | None:
    """임상 밴드로 flag 판정 - 밴드 정의된 항목만, 미정의 시 None(폴백)"""
    spec = BANDS.get(canonical)
    if spec is None:
        return None
    rules = spec.get(sex) if isinstance(spec, dict) else spec
    if not rules:
        return None
    for op, thr, flag in rules:
        if _OPS[op](value, thr):
            return flag
    return "normal"
