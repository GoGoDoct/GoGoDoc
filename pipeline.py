# -*- coding: utf-8 -*-
"""검진 결과 해석 파이프라인 (기획서 4.1 의 5단계 함수 체이닝).

기본은 샘플 데이터를 반환해 API 키 없이도 데모가 돌아간다.
실제 서비스로 붙일 때는 각 단계의 TODO 부분에 pdfplumber / OpenAI 호출을 채운다.

    단계 ①  파싱·추출      parse_pdf(file)              -> raw rows
    단계 ②  정상범위 매칭   match_reference(rows, ...)   -> 항목 + 상태 플래그
    단계 ③  해석·설명      interpret(items)             -> 쉬운 설명 부착
    단계 ④  안전·요약      apply_safety(items)          -> 면책/응급 처리
"""
import os
from sample_data import SAMPLE_ITEMS, EMERGENCY_ITEM

# 응급(패닉밸류) 기준 — 기획서 5장. 감지 시 즉시 내원 안내.
PANIC_VALUES = {
    "공복혈당": lambda v: v >= 500,
    "나트륨": lambda v: v < 120 or v > 160,
}

# 가드레일: 후처리에서 차단할 단정 표현
BANNED_PHRASES = ["암입니다", "병입니다", "확실히", "진단합니다"]

SYSTEM_PROMPT = (
    "당신은 건강검진 결과를 일반인에게 쉽게 설명하는 비서입니다. "
    "반드시 제공된 항목 해설 근거 안에서만 설명하고, 진단을 단정하지 마세요. "
    "모든 설명은 참고용이며 의료 진단이 아님을 전제로 합니다."
)


# ── 단계 ① 파싱·추출 ────────────────────────────────────
def parse_pdf(uploaded_file) -> list[dict]:
    """pdfplumber 로 표를 추출하고 OpenAI gpt-4o-mini 로 {항목,값,단위,참조범위} JSON 구조화.

    데모에서는 샘플 항목을 그대로 반환한다.
    """
    if uploaded_file is None:
        return [dict(it) for it in SAMPLE_ITEMS]

    # TODO(실서비스): pdfplumber + OpenAI gpt-4o-mini 구조화
    # import pdfplumber
    # with pdfplumber.open(uploaded_file) as pdf:
    #     tables = [t for page in pdf.pages for t in (page.extract_tables() or [])]
    # rows = _structure_with_openai(tables)   # Pydantic v2 model_validate_json
    # return rows
    return [dict(it) for it in SAMPLE_ITEMS]


# ── 단계 ② 정상범위 매칭 ────────────────────────────────
def match_reference(rows: list[dict], gender: str, age: int) -> list[dict]:
    """항목명 정규화(동의어 사전 + rapidfuzz fallback) 후 참조범위 대비 상태 플래그.

    성별·나이에 따라 참조범위가 달라지는 항목은 여기서 보정한다.
    데모 데이터는 이미 status 가 채워져 있어 그대로 사용한다.
    """
    out = []
    for r in rows:
        item = dict(r)
        if "status" not in item:  # 실데이터 경로
            item["status"] = _flag(item)
        out.append(item)
    return out


def _flag(item: dict) -> str:
    v, low, high = item["value"], item.get("low"), item.get("high")
    if low is not None and v < low:
        return "주의"
    if high is not None and v > high:
        # 기준 대비 초과 정도로 주의/이상 구분 (간단 규칙)
        return "이상" if v > high * 1.3 else "주의"
    return "정상"


# ── 단계 ③ 해석·설명 ────────────────────────────────────
def interpret(items: list[dict]) -> list[dict]:
    """OpenAI gpt-4o-mini 로 항목 해설 dict 근거를 인용하며 쉬운 설명 생성.

    데모 데이터는 explain 이 이미 들어 있다.
    """
    api_key = os.getenv("OPENAI_API_KEY")
    for it in items:
        if it.get("explain"):
            continue
        if api_key:
            it["explain"] = _interpret_with_openai(it, api_key)  # TODO
        else:
            it["explain"] = "해석을 생성하려면 OPENAI_API_KEY 가 필요합니다."
    return items


def _interpret_with_openai(item: dict, api_key: str) -> str:
    # TODO(실서비스): openai 클라이언트로 gpt-4o-mini 호출 (temperature=0.3)
    # from openai import OpenAI
    # client = OpenAI(api_key=api_key)
    # resp = client.chat.completions.create(model="gpt-4o-mini",
    #     messages=[{"role": "system", "content": SYSTEM_PROMPT}, ...])
    # return resp.choices[0].message.content
    return ""


# ── 단계 ④ 안전·요약 ────────────────────────────────────
def apply_safety(items: list[dict], emergency: bool = False) -> dict:
    """응급 이상치 감지, 단정 표현 필터링, 추적 항목 정리, 면책 강제."""
    if emergency:
        items = [dict(EMERGENCY_ITEM)] + items

    # 가드레일: 단정 표현 후처리 차단
    for it in items:
        text = it.get("explain", "")
        for bad in BANNED_PHRASES:
            text = text.replace(bad, "추적 관찰이 권장됩니다")
        it["explain"] = text

    # 응급 감지
    emergency_hit = next((it for it in items if it.get("status") == "응급"), None)
    if emergency_hit is None:
        for it in items:
            check = PANIC_VALUES.get(it["name"].split("(")[0])
            if check and check(it["value"]):
                it["status"] = "응급"
                emergency_hit = it
                break

    tracked = [it["name"] for it in items if it["status"] in ("주의", "이상", "응급")]
    return {
        "items": items,
        "emergency": emergency_hit,
        "tracked": tracked,
        "counts": {
            "정상": sum(1 for it in items if it["status"] == "정상"),
            "주의": sum(1 for it in items if it["status"] == "주의"),
            "이상": sum(1 for it in items if it["status"] in ("이상", "응급")),
        },
    }


# ── 오케스트레이션 (함수 체이닝) ────────────────────────
def run_pipeline(uploaded_file, gender: str, age: int, emergency: bool = False) -> dict:
    rows = parse_pdf(uploaded_file)
    items = match_reference(rows, gender, age)
    items = interpret(items)
    return apply_safety(items, emergency=emergency)
