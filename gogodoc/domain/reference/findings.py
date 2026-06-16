"""정성 소견 근거 KB - 비수치 검사(요단백·내시경·초음파·B형간염) 소견별 위험도·해설

수치 항목(reference_dict)과 달리 정상범위가 없는 정성 소견을 다룬다. 소견 텍스트를
키워드로 매칭(위에서부터 첫 매칭, 구체어 우선)해 flag·해설 근거를 반환한다. 미매칭 소견은
None - 상위에서 확인필요 폴백. 응급 소견은 없음(현 KB) - 모두 normal/caution/abnormal.

⚠ 위험도·해설은 일반 통용 기준 초안 - 실서비스 전 학회·검진기관 검수 필수.
"""

# item -> {"findings": [(키워드 튜플, flag, explanation, caution)], "source"}
# 키워드는 소견 텍스트 부분일치, 구체어(약양성)를 포괄어(양성)보다 먼저 배치
FINDINGS: dict[str, dict] = {
    "요단백": {
        "findings": [
            (("음성", "정상"), "normal", "소변 단백이 검출되지 않은 정상 소견", "정기검진 유지"),
            (("약양성", "±"), "caution",
             "소변 단백 미량 검출 - 일시적 요인(발열·운동·탈수)으로도 나타날 수 있음",
             "수분 섭취 후 재검 권장 - 반복 양성 시 신장 평가"),
            (("양성", "1+", "2+", "3+"), "abnormal",
             "소변 단백 양성 - 신장 사구체 기능 이상 가능성",
             "신장기능(크레아티닌·eGFR) 정밀검사 권장"),
        ],
        "source": "대한신장학회 단백뇨 안내",
    },
    "위내시경": {
        "findings": [
            (("정상", "이상 없음"), "normal", "위내시경상 특이 소견 없는 정상", "정기검진 유지"),
            (("위궤양", "궤양"), "abnormal", "위 점막 궤양 소견 - 출혈·천공 위험 평가 필요",
             "소화기내과 진료 - 헬리코박터 검사·치료 고려"),
            (("만성위염", "위염", "미란"), "caution", "위 점막 염증 소견 - 흔한 양성 소견",
             "자극적 음식·음주 절제, 증상 지속 시 진료"),
        ],
        "source": "대한소화기내시경학회 안내",
    },
    "대장내시경": {
        "findings": [
            (("정상", "이상 없음"), "normal", "대장내시경상 특이 소견 없는 정상", "정기검진 유지"),
            (("용종", "선종", "폴립"), "abnormal", "대장 용종 소견 - 일부는 시간이 지나며 변할 수 있어 제거·추적 권장",
             "소화기내과 진료 - 조직검사·절제 결과 확인"),
        ],
        "source": "대한대장항문학회 용종 안내",
    },
    "복부초음파": {
        "findings": [
            (("정상", "이상 없음"), "normal", "복부초음파상 특이 소견 없는 정상", "정기검진 유지"),
            (("지방간",), "caution", "간에 지방이 침착된 소견 - 생활습관 관련 흔한 양성 소견",
             "체중·음주·식이 관리, 간수치 동반 시 추적"),
            (("담낭용종", "담석", "용종"), "caution", "담낭 용종 소견 - 대부분 양성이나 크기 추적 필요",
             "정기 초음파 추적, 크기 증가 시 외과 진료"),
        ],
        "source": "대한초음파의학회 안내",
    },
    "B형간염 표면항원": {
        "findings": [
            (("음성", "비반응"), "normal", "B형간염 표면항원 음성 - 현재 감염 없음", "정기검진 유지"),
            (("양성", "반응", "보유"), "abnormal", "B형간염 표면항원 양성 - 바이러스 보유 상태",
             "소화기내과 진료 - 간기능·바이러스 정량 추적"),
        ],
        "source": "대한간학회 B형간염 안내",
    },
}


def lookup_finding(item: str, text: str) -> dict | None:
    """소견 텍스트 매칭 근거 카드 반환 - {flag, explanation, caution, source}, 미매칭 None"""
    spec = FINDINGS.get(item)
    if not spec or not text:
        return None
    for keywords, flag, explanation, caution in spec["findings"]:
        if any(kw in text for kw in keywords):
            return {
                "flag": flag,
                "explanation": explanation,
                "caution": caution,
                "source": spec["source"],
            }
    return None


def is_finding_item(item: str) -> bool:
    """정성 소견 KB 수록 항목 여부"""
    return item in FINDINGS
