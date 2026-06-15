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
    "ast": "AST",
    "got": "AST",
    "sgot": "AST",
    # 혈당
    "공복혈당": "공복혈당",
    "fbs": "공복혈당",
    "glucose": "공복혈당",
    "당화혈색소": "당화혈색소",
    "hba1c": "당화혈색소",
    # 콜레스테롤
    "총콜레스테롤": "총콜레스테롤",
    "total cholesterol": "총콜레스테롤",
    "hdl": "HDL 콜레스테롤",
    "ldl": "LDL 콜레스테롤",
    # 신장
    "bun": "BUN",
    "creatinine": "크레아티닌",
    "cr": "크레아티닌",
    "egfr": "eGFR",
}


def normalize_key(name: str) -> str:
    """매칭용 키 정규화 - 소문자화 및 공백 정리"""
    return name.strip().lower()
