"""응급 이상치(패닉 밸류) 기준 - 감지 시 즉시 내원 안내 우선 표시

패닉 밸류는 생명을 위협할 수 있어 즉각 조치가 필요한 검사값
조건: low(이하) 또는 high(이상) 임계값 - None 이면 해당 방향 미적용

출처 (D1 정의)
- 국제 임상검사실 critical value 통용 범위 (Labcorp, Mayo, ARUP 등 공통 구간)
- MSD 매뉴얼 전해질 균형 (저/고칼륨혈증)
- 기관마다 임계값이 다를 수 있어 보수적 통용값 채택, 데모용 기준
TODO: D2 이후 국내 검진기관 기준과 대조하여 임계값 검증
"""

# 표준 항목명 -> {low, high, message}
PANIC_VALUES: dict[str, dict] = {
    "공복혈당": {
        "low": 50,  # 저혈당 - 의식저하 위험
        "high": 500,  # 고혈당 - 케톤산증·고삼투압 위험
        "message": "혈당이 응급 수치입니다 - 즉시 의료기관 내원이 필요합니다",
    },
    "나트륨": {
        "low": 120,  # 저나트륨혈증 - 경련·의식저하 위험
        "high": 160,  # 고나트륨혈증 - 탈수·신경 손상 위험
        "message": "나트륨이 응급 수치입니다 - 즉시 의료기관 내원이 필요합니다",
    },
    "칼륨": {
        "low": 2.5,  # 저칼륨혈증 - 부정맥 위험
        "high": 6.5,  # 고칼륨혈증 - 심정지 위험
        "message": "칼륨이 응급 수치입니다 - 즉시 의료기관 내원이 필요합니다",
    },
    "칼슘": {
        "low": 6.0,  # 저칼슘혈증 - 경련·부정맥 위험
        "high": 13.0,  # 고칼슘혈증 - 의식저하·신부전 위험
        "message": "칼슘이 응급 수치입니다 - 즉시 의료기관 내원이 필요합니다",
    },
    "헤모글로빈": {
        "low": 7.0,  # 중증 빈혈 - 수혈 고려 수준
        "high": None,
        "message": "헤모글로빈이 응급 수치입니다 - 즉시 의료기관 내원이 필요합니다",
    },
    "크레아티닌": {
        "low": None,
        "high": 7.0,  # 중증 신부전 의심 수준
        "message": "크레아티닌이 응급 수치입니다 - 즉시 의료기관 내원이 필요합니다",
    },
}


def check_panic(canonical_name: str, value: float | None) -> str | None:
    """패닉 밸류 해당 시 안내 메시지 반환"""
    if value is None:
        return None
    rule = PANIC_VALUES.get(canonical_name)
    if not rule:
        return None
    low, high = rule.get("low"), rule.get("high")
    if (low is not None and value <= low) or (high is not None and value >= high):
        return rule["message"]
    return None
