"""항목 해설 dict - 표준 항목명별 정상범위·해설·주의사항

근거 기반 해석의 핵심 - LLM은 이 dict 범위 내에서만 설명 생성
정상범위는 성별·나이 룰 리스트로 관리 (D2 확장)
- 각 룰: {sex, age_min, age_max, low, high}
- sex "any" 는 성별 무관, 그 외 "male"/"female"
- 대상 사용자는 성인(직장인)이라 성인 밴드(19-120) 기준, 소아는 범위 외
select_range 가 (성별, 나이)에 맞는 (하한, 상한) 반환 - 미해당 시 None

출처 (D1 수집)
- 질병관리청 국가건강정보포털 https://health.kdca.go.kr
- 서울아산병원 의료정보 https://www.amc.seoul.kr
- 대한당뇨병학회 당뇨병 진료지침
- 대한고혈압학회 고혈압 진료지침
- 국민건강보험공단 건강검진 결과지 해설
TODO: D2 이후 PubMed MCP + ICD-10 Codes MCP 로 항목별 근거·질환코드 보강
"""

# 성인 나이 밴드 - 대상 사용자(직장인) 기준
_ADULT_MIN = 19
_ADULT_MAX = 120


def _adult(low, high, sex="any"):
    """성인 정상범위 룰 생성 헬퍼"""
    return {"sex": sex, "age_min": _ADULT_MIN, "age_max": _ADULT_MAX, "low": low, "high": high}


# 표준 항목명 -> 해설 정보 (ranges 는 성별·나이 룰 리스트)
REFERENCE: dict[str, dict] = {
    # 간기능
    "ALT": {
        "ranges": [_adult(0, 40)],
        "unit": "U/L",
        "explanation": "간세포가 손상되면 혈액으로 새어 나오는 효소로, 간 건강을 보는 대표 지표",
        "caution": "40 초과 시 간 기능 추적 관찰 권장, 음주·지방간·약물 영향 가능",
        "source": "질병관리청 국가건강정보포털 간기능검사",
    },
    "AST": {
        "ranges": [_adult(0, 40)],
        "unit": "U/L",
        "explanation": "간뿐 아니라 근육·심장에도 있는 효소로, 손상 시 올라가는 수치",
        "caution": "ALT 와 함께 해석 권장, AST 단독 상승은 근육 영향 가능",
        "source": "질병관리청 국가건강정보포털 간기능검사",
    },
    "감마지티피": {
        "ranges": [_adult(11, 63, "male"), _adult(8, 35, "female")],
        "unit": "IU/L",
        "explanation": "담즙 배설 통로에 있는 효소로, 음주·담도 이상에 민감하게 반응",
        "caution": "남성이 여성보다 기준이 높음, 상승 시 음주량 점검 및 추적 권장",
        "source": "연세대 의과대학 건강정보 감마글루타밀전이효소",
    },
    # 혈당
    "공복혈당": {
        "ranges": [_adult(70, 99)],
        "unit": "mg/dL",
        "explanation": "8시간 공복 후 잰 혈당으로, 당대사 상태를 보는 기본 지표",
        "caution": "100-125 공복혈당장애(당뇨 전단계), 126 이상 당뇨 의심 - 추적 권장",
        "source": "대한당뇨병학회 당뇨병 진료지침",
    },
    "당화혈색소": {
        "ranges": [_adult(4.0, 5.6)],
        "unit": "%",
        "explanation": "최근 2-3개월 평균 혈당을 반영하는 지표로, 식사 영향이 적음",
        "caution": "5.7-6.4 당뇨 전단계, 6.5 이상 당뇨 의심 - 추적 권장",
        "source": "대한당뇨병학회 당뇨병 진료지침",
    },
    # 지질
    "총콜레스테롤": {
        "ranges": [_adult(0, 200)],
        "unit": "mg/dL",
        "explanation": "혈중 전체 콜레스테롤 양으로, 심혈관 위험을 보는 기본 지표",
        "caution": "200 이상 경계, 240 이상 높음 - 식이·운동 관리 권장",
        "source": "서울대학교병원 의학정보 이상지질혈증",
    },
    "LDL 콜레스테롤": {
        "ranges": [_adult(0, 130)],
        "unit": "mg/dL",
        "explanation": "혈관 벽에 쌓여 동맥경화를 유발하는 나쁜 콜레스테롤",
        "caution": "130 이상 경계, 위험요인 있으면 더 낮은 목표 적용 - 추적 권장",
        "source": "서울대학교병원 의학정보 이상지질혈증",
    },
    "HDL 콜레스테롤": {
        # HDL 은 높을수록 좋음 - 하한 40 미만이 위험 신호
        "ranges": [_adult(40, 200)],
        "unit": "mg/dL",
        "explanation": "혈관의 콜레스테롤을 청소하는 좋은 콜레스테롤로, 높을수록 유리",
        "caution": "40 미만 낮음(위험), 60 이상 권장 - 운동·금연 도움",
        "source": "서울대학교병원 의학정보 이상지질혈증",
    },
    "중성지방": {
        "ranges": [_adult(0, 150)],
        "unit": "mg/dL",
        "explanation": "음식으로 섭취한 지방이 저장되는 형태로, 식사·음주에 민감",
        "caution": "150 이상 경계 - 공복 채혈 필요, 탄수화물·음주 조절 권장",
        "source": "서울대학교병원 의학정보 이상지질혈증",
    },
    # 신장
    "BUN": {
        "ranges": [_adult(8, 20)],
        "unit": "mg/dL",
        "explanation": "단백질 대사 노폐물인 요소질소로, 신장 배설 기능을 반영",
        "caution": "상승 시 신장 기능 저하·탈수 가능 - 크레아티닌과 함께 해석",
        "source": "서울아산병원 의료정보 신장기능검사",
    },
    "크레아티닌": {
        "ranges": [_adult(0.7, 1.4, "male"), _adult(0.5, 1.1, "female")],
        "unit": "mg/dL",
        "explanation": "근육 대사 노폐물로, 신장 여과 기능을 보는 핵심 지표",
        "caution": "근육량 영향으로 남성이 약간 높음, 상승 시 신장 기능 추적 권장",
        "source": "서울아산병원 의료정보 크레아티닌",
    },
    "eGFR": {
        # eGFR 은 높을수록 좋음 - 하한 미만이 신장 기능 저하
        "ranges": [_adult(90, 200)],
        "unit": "mL/min/1.73m²",
        "explanation": "신장이 1분간 걸러내는 혈액량 추정치로, 신장 기능의 종합 지표",
        "caution": "90 이상 정상, 60-89 경계, 60 미만 3개월 지속 시 만성콩팥병 의심",
        "source": "서울아산병원 의료정보 신장기능검사",
    },
    # 혈압
    "수축기혈압": {
        "ranges": [_adult(90, 120)],
        "unit": "mmHg",
        "explanation": "심장이 수축해 피를 내보낼 때의 혈압(높은 쪽 수치)",
        "caution": "120-129 주의, 130 이상 고혈압 전단계, 140 이상 고혈압 - 추적 권장",
        "source": "대한고혈압학회 고혈압 진료지침",
    },
    "이완기혈압": {
        "ranges": [_adult(60, 80)],
        "unit": "mmHg",
        "explanation": "심장이 이완해 피를 채울 때의 혈압(낮은 쪽 수치)",
        "caution": "80-89 고혈압 전단계, 90 이상 고혈압 - 추적 권장",
        "source": "대한고혈압학회 고혈압 진료지침",
    },
    # 혈액
    "헤모글로빈": {
        "ranges": [_adult(13, 17, "male"), _adult(12, 16, "female")],
        "unit": "g/dL",
        "explanation": "적혈구에서 산소를 운반하는 단백질로, 빈혈 여부를 보는 지표",
        "caution": "하한 미만 빈혈 의심 - 어지럼·피로 동반 시 추적 권장",
        "source": "서울아산병원 의료정보 일반혈액검사",
    },
    # 전해질 (응급 기준은 panic_values, 여기서 정상범위·해설 제공)
    "나트륨": {
        "ranges": [_adult(135, 145)],
        "unit": "mmol/L",
        "explanation": "체액 균형과 신경·근육 기능을 조절하는 주요 전해질",
        "caution": "이상 시 탈수·신장·호르몬 영향 가능 - 추적 권장, 극단값은 응급",
        "source": "서울아산병원 의료정보 전해질검사",
    },
    "칼륨": {
        "ranges": [_adult(3.5, 5.1)],
        "unit": "mmol/L",
        "explanation": "심장과 근육의 전기 활동을 조절하는 전해질",
        "caution": "이상 시 부정맥 위험 - 추적 권장, 극단값(2.5 이하·6.5 이상)은 응급",
        "source": "서울아산병원 의료정보 전해질검사",
    },
    "칼슘": {
        "ranges": [_adult(8.6, 10.2)],
        "unit": "mg/dL",
        "explanation": "뼈 건강과 근육·신경 기능에 필요한 무기질",
        "caution": "이상 시 부갑상선·신장·뼈 영향 가능 - 추적 권장",
        "source": "서울아산병원 의료정보 칼슘검사",
    },
    # 대사 - 요산
    "요산": {
        "ranges": [_adult(3.4, 7.0, "male"), _adult(2.4, 6.0, "female")],
        "unit": "mg/dL",
        "explanation": "퓨린 대사 산물로, 높으면 통풍·요로결석과 관련된 지표",
        "caution": "남성이 기준이 약간 높음, 상승 시 음주·고퓨린식 점검 및 추적 권장",
        "source": "서울아산병원 의료정보 요산검사",
    },
    # 계측 - 비만
    "BMI": {
        "ranges": [_adult(18.5, 22.9)],
        "unit": "kg/m²",
        "explanation": "키 대비 체중으로 비만 정도를 보는 체질량지수",
        "caution": "23-24.9 과체중, 25 이상 비만(대한비만학회 아시아 기준) - 식이·운동 관리 권장",
        "source": "대한비만학회 비만 진료지침",
    },
    "허리둘레": {
        # 복부비만 기준 상한만 의미 - 하한은 0
        "ranges": [_adult(0, 90, "male"), _adult(0, 85, "female")],
        "unit": "cm",
        "explanation": "복부(내장) 비만을 보는 지표로, 대사증후군 위험과 관련",
        "caution": "남성 90cm·여성 85cm 이상 복부비만 - 대사증후군 위험, 관리 권장",
        "source": "대한비만학회 비만 진료지침",
    },
}


def lookup(canonical_name: str) -> dict | None:
    """표준 항목명으로 해설 정보 조회"""
    return REFERENCE.get(canonical_name)


def select_range(entry: dict, sex: str, age: int) -> tuple[float, float] | None:
    """성별·나이에 맞는 정상범위 반환 - 첫 매칭 룰의 (하한, 상한), 미해당 시 None"""
    for rule in entry.get("ranges", []):
        if rule["sex"] not in ("any", sex):
            continue
        if not (rule["age_min"] <= age <= rule["age_max"]):
            continue
        return (rule["low"], rule["high"])
    return None
