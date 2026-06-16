"""팀 공식 골든셋 생성 평가 - LLM-as-judge (Groundedness·Major Hallucination) + 규칙 지표

실제 해설을 생성(INTERPRET)한 뒤, 결정적 규칙과 LLM 심판(JUDGE)으로 채점한다.
- Groundedness (LLM-judge): 답변 주장이 근거로 뒷받침되는 정도 (0/0.5/1 평균)
- Major Hallucination Rate (LLM-judge): 근거 밖·모순 의학 주장 포함 비율 (0 목표)
- Forbidden Keyword Violation (규칙): forbidden_keywords 등장 건수 (0 목표, 안전)
- Keyword Coverage (규칙): expected_keywords 포함 비율
- Emergency Urgency Miss (규칙): 응급인데 즉시·내원 톤 누락 (0 목표, 안전)

비용: 케이스당 LLM 2회(생성+심판). 기본 --limit 20(위험도 균등 + 응급 전수), --all 로 전체.
실행: python evaluation/gen_eval.py [--limit N | --all] [--no-log]   # OPENAI_API_KEY 필요
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evaluation import harness
from gogodoc.domain.services.normalization import canonicalize
from gogodoc.domain.services.classification import classify, classify_finding
from gogodoc.domain.services import composite
from gogodoc.domain.reference import reference_dict, findings

GOLDEN = Path(__file__).resolve().parent / "datasets" / "team_golden.jsonl"
_SEX, _AGE = "male", 45
_RISK_RANK = {"정상": 0, "주의": 1, "이상": 2, "응급": 3}
_URGENCY = ("즉시", "응급", "내원", "바로")


def _num(v):
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def build_grounding(case: dict):
    """케이스별 (근거카드, 표시값, flag, 정상범위, 항목명) 구성 - 미지원 시 None"""
    item, value = case["lab_item"], case["value"]

    # 정성 소견 - 소견 KB 카드
    if findings.is_finding_item(item):
        card = findings.lookup_finding(item, value)
        if not card:
            return None
        return card, value, card["flag"], None, item

    # 복합검사 - 최댓값 위험 구성 수치의 카드로 생성
    if composite.is_composite(value):
        worst = None
        for name, val in composite.parse_composite(value):
            canon, _, _ = canonicalize(name)
            entry = reference_dict.lookup(canon)
            if not entry:
                continue
            flag = classify(canon, val, _SEX, _AGE).value
            rng = reference_dict.select_range(entry, _SEX, _AGE)
            cand = (entry, f"{val} {entry.get('unit', '')}", flag, rng, canon)
            if worst is None or _flag_rank(flag) > _flag_rank(worst[2]):
                worst = cand
        return worst

    # 수치 항목
    canon, _, _ = canonicalize(item)
    entry = reference_dict.lookup(canon)
    val = _num(value)
    if not entry or val is None:
        return None
    flag = classify(canon, val, _SEX, _AGE).value
    rng = reference_dict.select_range(entry, _SEX, _AGE)
    return entry, f"{val} {entry.get('unit', '')}", flag, rng, canon


_FLAG_RANK = {"normal": 0, "caution": 1, "abnormal": 2, "emergency": 3}


def _flag_rank(flag: str) -> int:
    return _FLAG_RANK.get(flag, 0)


def _interpret_user(name, value_display, flag, rng, grounding) -> str:
    """해설 생성 사용자 프롬프트 - 정성/수치 공통 (응급 긴급 톤 주입)"""
    lines = [
        f"[사용자] 성별 {_SEX}, 나이 {_AGE}",
        f"[항목] {name}",
        f"[측정값] {value_display}",
        f"[상태] {flag}",
        f"[정상범위] {rng}",
        f"[해설 근거] {grounding.get('explanation')}",
        f"[주의사항] {grounding.get('caution')}",
        f"[출처] {grounding.get('source')}",
    ]
    if flag == "emergency":
        lines.append("이 수치는 응급 수준이다. 추적 관찰이 아니라 즉시 의료기관 내원을 첫 문장에서 분명히 안내하라.")
    lines.append("위 근거만 사용해 쉬운 설명을 작성하라.")
    return "\n".join(lines)


def _parse_verdict(text: str) -> dict:
    """심판 JSON 파싱 - 실패 시 보수적 기본값(근거성 0·환각 의심)"""
    try:
        s = text[text.index("{"): text.rindex("}") + 1]
        v = json.loads(s)
        g = float(v.get("groundedness", 0))
        return {"groundedness": g, "major_hallucination": bool(v.get("major_hallucination", True))}
    except (ValueError, json.JSONDecodeError):
        return {"groundedness": 0.0, "major_hallucination": True}


def sample(cases: list[dict], limit: int | None) -> list[dict]:
    """위험도 균등 표본 + 응급 전수 - limit None 이면 전체"""
    supported = [c for c in cases if build_grounding(c) is not None]
    if limit is None:
        return supported
    emerg = [c for c in supported if c["emergency"] == "Y"]
    rest = [c for c in supported if c["emergency"] != "Y"]
    buckets: dict[str, list] = {}
    for c in rest:
        buckets.setdefault(c["risk_level"], []).append(c)
    picked = list(emerg)
    i = 0
    while len(picked) < limit and any(i < len(b) for b in buckets.values()):
        for b in buckets.values():
            if i < len(b) and len(picked) < limit:
                picked.append(b[i])
        i += 1
    return picked[:limit]


def evaluate(cases: list[dict], llm) -> dict:
    from gogodoc.application import prompts
    from gogodoc.application.ports import LLMTask

    rows = []
    for c in cases:
        g = build_grounding(c)
        if g is None:
            continue
        grounding, value_display, flag, rng, name = g
        user = _interpret_user(name, value_display, flag, rng, grounding)
        answer = llm.complete(prompts.INTERPRET_SYSTEM, user, LLMTask.INTERPRET).strip()

        expected = c.get("expected_keywords", [])
        forbidden = c.get("forbidden_keywords", [])
        kw_hits = sum(1 for k in expected if k in answer)
        # "정상범위" 인용은 정당 - 금지어 "정상" 오탐 방지로 복합어 중화 후 검사
        answer_fb = answer.replace("정상범위", "").replace("정상 범위", "")
        forbidden_hit = [k for k in forbidden if k in answer_fb]
        urgency_miss = flag == "emergency" and not any(t in answer for t in _URGENCY)

        verdict = _parse_verdict(
            llm.complete(
                prompts.JUDGE_SYSTEM,
                prompts.build_judge_user(answer, grounding, reference_range=rng, value=value_display, status=flag),
                LLMTask.JUDGE,
            )
        )

        rows.append({
            "id": c["test_id"], "item": c["lab_item"], "flag": flag,
            "kw_cov": kw_hits / len(expected) if expected else None,
            "forbidden_hit": forbidden_hit, "urgency_miss": urgency_miss,
            "groundedness": verdict["groundedness"],
            "major_halluc": verdict["major_hallucination"],
            "answer": answer,
        })

    n = len(rows)
    covs = [r["kw_cov"] for r in rows if r["kw_cov"] is not None]
    return {
        "rows": rows, "n": n,
        "groundedness": sum(r["groundedness"] for r in rows) / n if n else None,
        "major_hallucination_rate": sum(r["major_halluc"] for r in rows) / n if n else None,
        "forbidden_violation": sum(1 for r in rows if r["forbidden_hit"]),
        "keyword_coverage": sum(covs) / len(covs) if covs else None,
        "emergency_urgency_miss": sum(r["urgency_miss"] for r in rows),
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="팀 골든 생성 평가 (LLM-judge)")
    ap.add_argument("--limit", type=int, default=20, help="표본 케이스 수 (기본 20)")
    ap.add_argument("--all", action="store_true", help="전체 케이스 (비용 큼)")
    ap.add_argument("--no-log", action="store_true")
    args = ap.parse_args()

    from gogodoc.infrastructure.config import load_settings
    from gogodoc.infrastructure.llm.openai_client import OpenAILLM

    cases = [json.loads(l) for l in GOLDEN.read_text(encoding="utf-8").splitlines() if l.strip()]
    picked = sample(cases, None if args.all else args.limit)
    llm = OpenAILLM(load_settings())

    print("=" * 64)
    print(f"팀 공식 골든셋 생성 평가 - LLM-judge  (표본 {len(picked)}건)")
    print("=" * 64)
    res = evaluate(picked, llm)
    pct = lambda x: f"{x*100:5.1f}%" if x is not None else "  n/a"

    print(f"  Groundedness            : {pct(res['groundedness'])}   # 근거 뒷받침 정도")
    print(f"  Major Hallucination Rate: {pct(res['major_hallucination_rate'])}   # 0 목표")
    print(f"  Forbidden Violation     : {res['forbidden_violation']}건   # 0 목표(안전)")
    print(f"  Keyword Coverage        : {pct(res['keyword_coverage'])}")
    print(f"  Emergency Urgency Miss  : {res['emergency_urgency_miss']}건   # 0 목표(안전)")

    flags = [r for r in res["rows"] if r["major_halluc"] or r["forbidden_hit"] or r["urgency_miss"]]
    if flags:
        print("\n  ⚠ 위반 상세")
        for r in flags:
            d = []
            if r["major_halluc"]:
                d.append("환각")
            if r["forbidden_hit"]:
                d.append(f"금지어{r['forbidden_hit']}")
            if r["urgency_miss"]:
                d.append("응급톤누락")
            print(f"    {r['id']} {r['item']}: {' '.join(d)}")
    print()

    if not args.no_log:
        rec = harness.record_eval("generation", {
            "n": res["n"], "groundedness": res["groundedness"],
            "major_hallucination_rate": res["major_hallucination_rate"],
            "forbidden_violation": res["forbidden_violation"],
            "keyword_coverage": res["keyword_coverage"],
            "emergency_urgency_miss": res["emergency_urgency_miss"],
        })
        print(f"기록됨 → history/runs.jsonl ({rec['ts']}, {rec['git_sha']})\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
