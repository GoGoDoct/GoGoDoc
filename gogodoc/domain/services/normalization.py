"""항목명 정규화 - 동의어 매핑 및 퍼지 매칭

순수 도메인 규칙 - rapidfuzz 는 IO 없는 결정적 알고리즘 라이브러리로 예외 허용
"""

from rapidfuzz import process, fuzz

from gogodoc.domain.reference import synonyms

# rapidfuzz fallback 최소 점수
_FUZZY_THRESHOLD = 80.0


def canonicalize(raw_name: str) -> tuple[str, float, bool]:
    """원본 항목명을 표준명으로 변환 - (표준명, 점수, 매칭여부)"""
    key = synonyms.normalize_key(raw_name)

    # 동의어 사전 직접 매칭
    if key in synonyms.SYNONYMS:
        return synonyms.SYNONYMS[key], 100.0, True

    # rapidfuzz fallback - 동의어 키 대상 퍼지 매칭
    candidates = list(synonyms.SYNONYMS.keys())
    best = process.extractOne(key, candidates, scorer=fuzz.WRatio)
    if best and best[1] >= _FUZZY_THRESHOLD:
        return synonyms.SYNONYMS[best[0]], float(best[1]), True

    # 미매칭 - 원본명 유지
    return raw_name, 0.0, False
