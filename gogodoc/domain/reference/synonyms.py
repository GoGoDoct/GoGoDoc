"""동의어 사전 - 기관별 항목명·약어를 표준 항목명으로 통일

D1 선처리 대상 - 데모 안정성의 1순위 요인
변형명(한글명/영문약어/단위 변형)을 표준 항목명에 매핑
"""

# 변형명 -> 표준 항목명
# TODO: D1 샘플 결과지 3-5종에서 실제 표기 변형 수집 후 확장
SYNONYMS: dict[str, str] = {
    # 간수치
    "alt": "ALT",
    "gpt": "ALT",
    "sgpt": "ALT",
    "alanine aminotransferase": "ALT",
    "alanine transaminase": "ALT",
    "alat": "ALT",
    "ast": "AST",
    "got": "AST",
    "sgot": "AST",
    "aspartate aminotransferase": "AST",
    "aspartate transaminase": "AST",
    "asat": "AST",
    # 감마지티피 (γ-GTP) - 표기 변형 다수
    "감마지티피": "감마지티피",
    "ggt": "감마지티피",
    "ggtp": "감마지티피",
    "γ-gtp": "감마지티피",
    "r-gtp": "감마지티피",  # γ 를 r 로 표기하는 결과지
    "y-gtp": "감마지티피",  # γ 를 y 로 OCR 한 경우
    "감마gtp": "감마지티피",
    "gamma-gtp": "감마지티피",
    "gamma glutamyl transferase": "감마지티피",
    "gamma glutamyl transpeptidase": "감마지티피",
    "감마글루타밀전이효소": "감마지티피",
    "감마글루타밀 전이효소": "감마지티피",
    # 혈당
    "공복혈당": "공복혈당",
    "fbs": "공복혈당",
    "glucose": "공복혈당",
    "fasting glucose": "공복혈당",
    "fasting blood glucose": "공복혈당",
    "fbg": "공복혈당",
    "당화혈색소": "당화혈색소",
    "hba1c": "당화혈색소",
    "a1c": "당화혈색소",
    "glycated hemoglobin": "당화혈색소",
    "glycohemoglobin": "당화혈색소",
    "당화 헤모글로빈": "당화혈색소",
    # 콜레스테롤
    "총콜레스테롤": "총콜레스테롤",
    "total cholesterol": "총콜레스테롤",
    "total chol": "총콜레스테롤",
    "cholesterol total": "총콜레스테롤",
    "tc": "총콜레스테롤",
    "t-chol": "총콜레스테롤",
    "hdl": "HDL 콜레스테롤",
    "hdl-c": "HDL 콜레스테롤",
    "hdl cholesterol": "HDL 콜레스테롤",
    "hdl-cholesterol": "HDL 콜레스테롤",
    "ldl": "LDL 콜레스테롤",
    "ldl-c": "LDL 콜레스테롤",
    "ldl cholesterol": "LDL 콜레스테롤",
    "ldl-cholesterol": "LDL 콜레스테롤",
    "중성지방": "중성지방",
    "tg": "중성지방",
    "triglyceride": "중성지방",
    "triglycerides": "중성지방",
    "triacylglycerol": "중성지방",
    "트리글리세라이드": "중성지방",
    # 신장
    "bun": "BUN",
    "creatinine": "크레아티닌",
    "cr": "크레아티닌",
    "crea": "크레아티닌",
    "serum creatinine": "크레아티닌",
    "egfr": "eGFR",
    "gfr": "eGFR",
    "사구체여과율": "eGFR",
    "estimated gfr": "eGFR",
    "estimated glomerular filtration rate": "eGFR",
    "추정사구체여과율": "eGFR",
    # 혈압
    "수축기혈압": "수축기혈압",
    "sbp": "수축기혈압",
    "수축기": "수축기혈압",
    "이완기혈압": "이완기혈압",
    "dbp": "이완기혈압",
    "이완기": "이완기혈압",
    # 혈액 - 헤모글로빈(혈색소)
    "헤모글로빈": "헤모글로빈",
    "혈색소": "헤모글로빈",
    "hb": "헤모글로빈",
    "hgb": "헤모글로빈",
    "hemoglobin": "헤모글로빈",
    "haemoglobin": "헤모글로빈",
    "hemoglobin concentration": "헤모글로빈",
    # 전해질
    "나트륨": "나트륨",
    "na": "나트륨",
    "sodium": "나트륨",
    "칼륨": "칼륨",
    "k": "칼륨",
    "potassium": "칼륨",
    "칼슘": "칼슘",
    "ca": "칼슘",
    "calcium": "칼슘",
    # 대사 - 요산
    "요산": "요산",
    "ua": "요산",
    "uric acid": "요산",
    "uric-acid": "요산",
    # 계측 - 비만
    "bmi": "BMI",
    "체질량지수": "BMI",
    "허리둘레": "허리둘레",
    "복부둘레": "허리둘레",
    "waist": "허리둘레",
    # 갑상선
    "tsh": "TSH",
    "갑상선자극호르몬": "TSH",
    # 혈액 - CBC 보강
    "백혈구": "백혈구",
    "wbc": "백혈구",
    "white blood cell": "백혈구",
    "white blood cells": "백혈구",
    "leukocyte": "백혈구",
    "wbc count": "백혈구",
    "백혈구수": "백혈구",
    "혈소판": "혈소판",
    "plt": "혈소판",
    "platelet": "혈소판",
    "platelet count": "혈소판",
    "thrombocyte": "혈소판",
    "혈소판수": "혈소판",
    # 종양표지자
    "cea": "CEA",
    "afp": "AFP",
    "ca19-9": "CA19-9",
    "ca199": "CA19-9",
    "ca-19-9": "CA19-9",
    "psa": "PSA",
    "전립선특이항원": "PSA",
}


def normalize_key(name: str) -> str:
    """매칭용 키 정규화 - 소문자화 및 공백 정리"""
    return name.strip().lower()
